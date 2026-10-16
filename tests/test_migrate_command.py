"""
Tests for the `migrate_recurrences` Django management command.
"""

from __future__ import annotations

import json
from datetime import datetime
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models

import recurrence
from tests.models import (
    EventWithJSCalendarStorage,
    EventWithNoNulls,
    EventWithNulls,
)


def _get_raw_recurs(model_cls: type[models.Model], pk: int) -> str | None:
    raw_expr = models.Func(
        models.F("recurs"),
        template="%(expressions)s",
        output_field=models.TextField(),
    )
    return (
        model_cls.objects.annotate(_raw=raw_expr)
        .filter(pk=pk)
        .values_list("_raw", flat=True)
        .first()
    )


@pytest.mark.django_db
def test_migrate_recurrences_dry_run_and_live_migration():
    ev1 = EventWithNoNulls.objects.create(
        recurs="DTSTART:20260105T090000Z\nRRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4"
    )
    EventWithNulls.objects.create(recurs=None)
    EventWithJSCalendarStorage.objects.create(
        recurs=recurrence.Recurrence(rrules=[recurrence.Rule(recurrence.DAILY)])
    )

    assert _get_raw_recurs(EventWithNoNulls, ev1.pk).startswith("DTSTART:")

    # 1. Dry-run with JSON output does not mutate the database
    out = StringIO()
    call_command("migrate_recurrences", dry_run=True, json_output=True, stdout=out)
    report = json.loads(out.getvalue())

    assert report["dry_run"] is True
    assert report["target_format"] == "rfc8984"
    assert report["scanned"] == 3
    assert report["migrated"] == 1
    assert report["already_target_format"] == 1
    assert report["skipped_empty"] == 1
    assert report["errors"] == 0
    assert _get_raw_recurs(EventWithNoNulls, ev1.pk).startswith("DTSTART:")

    # 2. Live migration converts legacy RFC 5545 row to RFC 8984 JSON
    out_live = StringIO()
    call_command(
        "migrate_recurrences",
        model_spec="tests.EventWithNoNulls.recurs",
        include_defaults=True,
        json_output=True,
        stdout=out_live,
    )
    live_report = json.loads(out_live.getvalue())
    assert live_report["migrated"] == 1

    raw_after = _get_raw_recurs(EventWithNoNulls, ev1.pk)
    assert raw_after is not None
    parsed_json = json.loads(raw_after)
    assert parsed_json["@type"] == "Event"
    assert parsed_json["recurrenceRules"][0]["frequency"] == "weekly"
    assert parsed_json["recurrenceRules"][0]["rscale"] == "gregorian"

    # Reload via Django ORM and verify occurrences are identical
    ev1.refresh_from_db()
    assert ev1.recurs.count() == 4
    assert next(iter(ev1.recurs.occurrences())) == datetime(2026, 1, 5, 9, 0, 0)

    # 3. Running again is idempotent (already_target_format == 1, migrated == 0)
    out_idem = StringIO()
    call_command(
        "migrate_recurrences",
        model_spec="tests.EventWithNoNulls",
        json_output=True,
        stdout=out_idem,
    )
    idem_report = json.loads(out_idem.getvalue())
    assert idem_report["migrated"] == 0
    assert idem_report["already_target_format"] == 1

    # 4. Rollback migration to rfc5545
    out_rollback = StringIO()
    call_command(
        "migrate_recurrences",
        model_spec="tests.EventWithNoNulls",
        target_format="rfc5545",
        stdout=out_rollback,
    )
    assert "Recurrence migration to RFC5545 complete" in out_rollback.getvalue()
    assert _get_raw_recurs(EventWithNoNulls, ev1.pk).startswith("DTSTART:")

    # Running rfc5545 migration again is idempotent
    out_rollback_idem = StringIO()
    call_command(
        "migrate_recurrences",
        model_spec="tests.EventWithNoNulls",
        target_format="rfc5545",
        json_output=True,
        stdout=out_rollback_idem,
    )
    rollback_idem_report = json.loads(out_rollback_idem.getvalue())
    assert rollback_idem_report["already_target_format"] == 1


@pytest.mark.django_db
def test_migrate_recurrences_error_handling_and_strict_mode():
    ev = EventWithNulls.objects.create(recurs="RRULE:FREQ=DAILY")
    # Bypass validation via .update() to simulate a corrupted legacy row in the DB
    EventWithNulls.objects.filter(pk=ev.pk).update(recurs="CORRUPTED_DATA")

    out = StringIO()
    err = StringIO()
    call_command(
        "migrate_recurrences",
        model_spec="tests.EventWithNulls",
        stdout=out,
        stderr=err,
    )
    assert "errors=1" in out.getvalue()
    assert "CORRUPTED_DATA" in err.getvalue() or "malformed data" in err.getvalue()

    with pytest.raises(CommandError):
        call_command(
            "migrate_recurrences",
            model_spec="tests.EventWithNulls",
            strict=True,
        )

    with pytest.raises(CommandError):
        call_command("migrate_recurrences", model_spec="invalid_spec")

    with pytest.raises(CommandError):
        call_command("migrate_recurrences", model_spec="nonexistent.Model")

    with pytest.raises(CommandError):
        call_command("migrate_recurrences", model_spec="tests.EventWithNulls.nonexistent_field")
