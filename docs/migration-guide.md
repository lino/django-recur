# Migration Guide (`django-recurrence` → `django-recurrence-jscalendar`)

`django-recurrence-jscalendar` is architected so that existing projects using [`jazzband/django-recurrence`](https://github.com/jazzband/django-recurrence) can upgrade in **three progressive stages**:

1. **Stage 1: Zero-Change Drop-In Swap** (keep existing models, imports, and database rows).
2. **Stage 2: In-Place Database Migration to RFC 8984 JSON** using `python manage.py migrate_recurrences`.
3. **Stage 3 (Optional): Adopt Native `JSCalendarRecurrenceField`** (`JSONField`-backed) for JSON indexing and native RFC 8984 features.

---

## Stage 1: Drop-In Package Replacement

Replace `django-recurrence` in your dependencies with `django-recurrence-jscalendar`:

```bash
uv remove django-recurrence
uv add django-recurrence-jscalendar
```

Add `"dj_recurrence"` alongside `"recurrence"` in `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "recurrence",
    "dj_recurrence",
]
```

**No model changes or database migrations are required in Stage 1.**
`recurrence.fields.RecurrenceField` transparently reads:

- Legacy RFC 2445 / RFC 5545 strings (`RRULE:FREQ=WEEKLY;BYDAY=MO,WE`)
- RFC 8984 JSCalendar JSON strings (`{"@type": "JSCalendarRecurrence", ...}`)
- Python `recurrence.Recurrence`, `recurrence.Rule`, `dj_recurrence.JSCalendarRecurrence`, or `dict` objects

---

## Stage 2: Migrating Stored Database Rules to RFC 8984 (`migrate_recurrences`)

Once `django-recurrence-jscalendar` is deployed, use the built-in `migrate_recurrences` management command to convert all legacy RFC 2445 / RFC 5545 strings in your database to RFC 8984 JSCalendar JSON.

### 1. Run a Dry Run with Audit Report

Preview all models and rows that will be migrated without writing to the database:

```bash
python manage.py migrate_recurrences --dry-run
```

For machine-readable CI/CD auditing, pass `--json`:

```bash
python manage.py migrate_recurrences --dry-run --json
```

Example JSON output:

```json
{
  "target_format": "rfc8984",
  "dry_run": true,
  "totals": {
    "scanned": 142,
    "converted": 140,
    "already_migrated": 2,
    "skipped_empty": 0,
    "failed": 0
  },
  "fields": [
    {
      "model": "events.Event",
      "field": "recurrences",
      "scanned": 142,
      "converted": 140,
      "already_migrated": 2,
      "skipped_empty": 0,
      "failed": 0,
      "issues": [],
      "errors": []
    }
  ]
}
```

### 2. Execute the Database Migration

Run the migration across all models (or target specific models/fields with `--model`):

```bash
# Migrate all models with RecurrenceField or JSCalendarRecurrenceField
python manage.py migrate_recurrences

# Or migrate a specific app/model or field
python manage.py migrate_recurrences --model events.Event --model events.Course.schedule
```

### 3. Switch Default Storage Format to RFC 8984

In `settings.py`, configure `RecurrenceField` to write RFC 8984 JSCalendar JSON for all future saves:

```python
RECURRENCE_STORAGE_FORMAT = "rfc8984"
```

### Command-Line Options Reference

| Option | Default | Description |
| --- | --- | --- |
| `--model <label>` | All models | Restrict migration to `app_label.ModelName` or `app_label.ModelName.field_name`. Repeatable. |
| `--dry-run` | `False` | Parse, convert, and validate all rows without writing changes to the database. |
| `--target-format` | `"rfc8984"` | Target serialization format: `"rfc8984"` (JSCalendar JSON) or `"rfc5545"` (iCalendar text rollback). |
| `--batch-size` | `500` | Number of rows processed per database batch. |
| `--include-defaults` | `False` | Include default RFC 8984 values (`interval: 1`, `rscale: "gregorian"`, etc.) in JSON output. |
| `--strict` | `False` | Abort with `CommandError` if any conversion warning or parse error occurs. |
| `--json` | `False` | Output a structured JSON summary report. |

---

## Stage 3: Using `JSCalendarRecurrenceField` directly

For new models—or when migrating existing text columns to native PostgreSQL/SQLite `JSONField`—use `dj_recurrence.fields.JSCalendarRecurrenceField`:

```python
from dj_recurrence.fields import JSCalendarRecurrenceField


class Event(models.Model):
    recurrences = JSCalendarRecurrenceField()
```

Because `JSCalendarRecurrenceField` subclasses `django.db.models.JSONField`, it stores structured JSON natively in the database while returning rich `JSCalendarRecurrence` instances in Python.
