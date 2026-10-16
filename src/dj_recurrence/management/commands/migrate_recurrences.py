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
from django.db import models, transaction

from dj_recurrence import exceptions
from dj_recurrence.fields import JSCalendarRecurrenceField
from dj_recurrence.rfc5545 import deserialize_any


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

        summary: dict[str, Any] = {
            "target_format": target_format,
            "dry_run": dry_run,
            "fields_inspected": len(target_fields),
            "scanned": 0,
            "migrated": 0,
            "already_target_format": 0,
            "skipped_empty": 0,
            "errors": 0,
            "error_details": [],
        }

        for model_cls, field in target_fields:
            include_dtstart = getattr(field, "include_dtstart", True)
            is_json_field = isinstance(field, JSCalendarRecurrenceField)

            raw_expr: Any = models.Func(
                models.F(field.name),
                template="%(expressions)s",
                output_field=models.TextField(),
            )
            qs = model_cls._default_manager.annotate(_raw_recurrence_val=raw_expr).order_by("pk")
            rows = list(qs.values_list("pk", "_raw_recurrence_val").iterator(chunk_size=batch_size))

            with transaction.atomic():
                for pk, raw_val in rows:
                    summary["scanned"] += 1

                    if raw_val is None or raw_val == "" or raw_val == "null":
                        summary["skipped_empty"] += 1
                        continue

                    currently_jscalendar = is_jscalendar_payload(raw_val)
                    try:
                        rec_obj = deserialize_any(raw_val, include_dtstart=include_dtstart)
                    except (exceptions.RecurrenceError, ValueError, TypeError) as exc:
                        summary["errors"] += 1
                        detail = f"{model_cls._meta.label} pk={pk} field={field.name}: {exc}"
                        summary["error_details"].append(detail)
                        if strict:
                            raise CommandError(detail) from exc
                        continue

                    if target_format == "rfc8984" and currently_jscalendar:
                        summary["already_target_format"] += 1
                        continue
                    if target_format == "rfc5545" and not currently_jscalendar:
                        summary["already_target_format"] += 1
                        continue

                    if target_format == "rfc8984":
                        new_val: Any = (
                            rec_obj.to_jscalendar(include_defaults=include_defaults)
                            if is_json_field
                            else rec_obj.to_json(include_defaults=include_defaults)
                        )
                    else:
                        new_val = rec_obj.to_icalendar()

                    if not dry_run:
                        model_cls._default_manager.filter(pk=pk).update(**{field.attname: new_val})
                    summary["migrated"] += 1

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
                f"errors={summary['errors']}"
            )
        )
        for err in summary["error_details"]:
            self.stderr.write(self.style.ERROR(f"  - {err}"))
        return None
