"""
Django management command to migrate recurrence rules in the database from
legacy RFC 2445 / RFC 5545 text format to RFC 8984 (JSCalendar) JSON format.
"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models, router, transaction

from django_recur import exceptions
from django_recur.fields import JSCalendarRecurrenceField
from django_recur.rfc5545 import (
    convert_icalendar_to_jscalendar_with_report,
    convert_jscalendar_to_icalendar_with_report,
    deserialize_any,
)


def is_jscalendar_payload(raw_value: Any) -> bool:
    """Return True if ``raw_value`` is already an RFC 8984 JSCalendar dict or JSON string."""
    if isinstance(raw_value, dict):
        return True
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
                return isinstance(parsed, dict)
            except json.JSONDecodeError:
                return False
    return False


class Command(BaseCommand):
    help = (
        "Migrate recurrence fields in the database between legacy RFC 2445/5545 "
        "iCalendar strings and RFC 8984 JSCalendar JSON."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--model",
            dest="model_spec",
            default=None,
            help=(
                "Optional target specification in the form 'app_label.ModelName' "
                "or 'app_label.ModelName.field_name'. If omitted, all models with "
                "RecurrenceField or JSCalendarRecurrenceField are inspected."
            ),
        )
        parser.add_argument(
            "--target-format",
            choices=["rfc8984", "rfc5545"],
            default="rfc8984",
            help="Target serialization format to write (default: rfc8984).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Inspect and validate all records without writing changes to the database.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of rows to process per batch (default: 500).",
        )
        parser.add_argument(
            "--include-defaults",
            action="store_true",
            default=False,
            help="Include default RFC 8984 property values in serialized JSON.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            default=False,
            help="Abort immediately on the first deserialization error.",
        )
        parser.add_argument(
            "--json",
            dest="json_output",
            action="store_true",
            default=False,
            help="Output migration summary as a JSON object.",
        )

    def _discover_target_fields(
        self, model_spec: str | None
    ) -> list[tuple[type[models.Model], models.Field[Any, Any]]]:
        from recurrence.fields import RecurrenceField as LegacyRecurrenceField

        target_fields: list[tuple[type[models.Model], models.Field[Any, Any]]] = []

        if model_spec:
            parts = model_spec.split(".")
            if len(parts) not in (2, 3):
                raise CommandError(
                    f"Invalid --model specification {model_spec!r}. "
                    "Expected 'app_label.ModelName' or 'app_label.ModelName.field_name'."
                )
            app_label, model_name = parts[0], parts[1]
            field_filter = parts[2] if len(parts) == 3 else None

            try:
                model_cls = apps.get_model(app_label, model_name)
            except LookupError as exc:
                raise CommandError(f"Model '{app_label}.{model_name}' not found.") from exc

            for f in model_cls._meta.get_fields():
                if isinstance(f, (LegacyRecurrenceField, JSCalendarRecurrenceField)) and (
                    field_filter is None or f.name == field_filter
                ):
                    target_fields.append((model_cls, f))

            if field_filter and not target_fields:
                raise CommandError(
                    f"Field '{field_filter}' on '{app_label}.{model_name}' is not a "
                    "RecurrenceField or JSCalendarRecurrenceField."
                )
            return target_fields

        for model_cls in apps.get_models():
            if model_cls._meta.abstract or model_cls._meta.proxy:
                continue
            for f in model_cls._meta.get_fields():
                if isinstance(f, (LegacyRecurrenceField, JSCalendarRecurrenceField)):
                    target_fields.append((model_cls, f))

        return target_fields

    def handle(self, *args: Any, **options: Any) -> str | None:
        model_spec: str | None = options["model_spec"]
        target_format: str = options["target_format"]
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]
        include_defaults: bool = options.get("include_defaults", False)
        strict: bool = options["strict"]
        json_output: bool = options["json_output"]

        target_fields = self._discover_target_fields(model_spec)
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")
        if target_format == "rfc5545":
            native_fields = [
                field for _, field in target_fields if isinstance(field, JSCalendarRecurrenceField)
            ]
            if model_spec and native_fields:
                raise CommandError(
                    "RFC5545 rollback requires a legacy RecurrenceField text column."
                )
            target_fields = [
                (model_cls, field)
                for model_cls, field in target_fields
                if not isinstance(field, JSCalendarRecurrenceField)
            ]

        summary: dict[str, Any] = {
            "target_format": target_format,
            "dry_run": dry_run,
            "fields_inspected": len(target_fields),
            "scanned": 0,
            "migrated": 0,
            "already_target_format": 0,
            "conversion_warnings": 0,
            "warning_details": [],
            "skipped_empty": 0,
            "errors": 0,
            "error_details": [],
        }

        for model_cls, field in target_fields:
            include_dtstart = getattr(field, "include_dtstart", True)
            is_json_field = isinstance(field, JSCalendarRecurrenceField)

            output_field = models.JSONField() if is_json_field else models.TextField()
            raw_expr = models.ExpressionWrapper(
                models.F(field.name),
                output_field=output_field,
            )
            db = router.db_for_write(model_cls)
            manager = model_cls._base_manager.db_manager(db)
            qs = manager.annotate(_raw_recurrence_val=raw_expr).order_by("pk")
            if not dry_run:
                qs = qs.select_for_update()
            rows = qs.values_list("pk", "_raw_recurrence_val")

            with transaction.atomic(using=db):
                page = list(rows[:batch_size])
                while page:
                    for pk, raw_val in page:
                        summary["scanned"] += 1
                        if raw_val is None or raw_val in ("", "null"):
                            summary["skipped_empty"] += 1
                            continue

                        detail = f"{model_cls._meta.label} pk={pk} field={field.name}"
                        currently_jscalendar = is_jscalendar_payload(raw_val)
                        try:
                            if currently_jscalendar:
                                rec_obj = deserialize_any(raw_val, include_dtstart=include_dtstart)
                            else:
                                report = convert_icalendar_to_jscalendar_with_report(
                                    raw_val, include_dtstart=include_dtstart
                                )
                                rec_obj = report.output
                                if target_format == "rfc8984" and not report.lossless:
                                    raise exceptions.ConversionError(
                                        "Lossy import: "
                                        + "; ".join(issue.message for issue in report.issues)
                                    )

                            already_target_format = (
                                (
                                    isinstance(raw_val, dict)
                                    if is_json_field
                                    else currently_jscalendar
                                )
                                if target_format == "rfc8984"
                                else not currently_jscalendar
                            )
                            if already_target_format:
                                summary["already_target_format"] += 1
                                continue

                            if target_format == "rfc8984":
                                new_val = (
                                    rec_obj.to_jscalendar(include_defaults=include_defaults)
                                    if is_json_field
                                    else rec_obj.to_json(include_defaults=include_defaults)
                                )
                            else:
                                report = convert_jscalendar_to_icalendar_with_report(
                                    rec_obj, strict=strict, include_rscale=True
                                )
                                new_val = report.output
                                if not report.lossless:
                                    summary["conversion_warnings"] += 1
                                    summary["warning_details"].append(
                                        f"{detail}: "
                                        + "; ".join(issue.message for issue in report.issues)
                                    )
                        except (exceptions.RecurrenceError, ValueError, TypeError) as exc:
                            summary["errors"] += 1
                            message = f"{detail}: {exc}"
                            summary["error_details"].append(message)
                            if strict:
                                raise CommandError(message) from exc
                            continue

                        if not dry_run:
                            manager.filter(pk=pk).update(
                                **{field.attname: models.Value(new_val, output_field=output_field)}
                            )
                        summary["migrated"] += 1

                    page = list(rows.filter(pk__gt=page[-1][0])[:batch_size])

        if json_output:
            output_str = json.dumps(summary, indent=2)
            self.stdout.write(output_str)
            return None

        mode_str = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode_str}Recurrence migration to {target_format.upper()} complete: "
                f"scanned={summary['scanned']}, "
                f"migrated={summary['migrated']}, "
                f"already_target_format={summary['already_target_format']}, "
                f"skipped_empty={summary['skipped_empty']}, "
                f"errors={summary['errors']}, warnings={summary['conversion_warnings']}"
            )
        )
        for err in summary["error_details"]:
            self.stderr.write(self.style.ERROR(f"  - {err}"))
        for warning in summary["warning_details"]:
            self.stderr.write(self.style.WARNING(f"  - {warning}"))
        return None
