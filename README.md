# django-recur

[![CI](https://github.com/lino/django-recur/actions/workflows/ci.yml/badge.svg)](https://github.com/lino/django-recur/actions/workflows/ci.yml)
[![Documentation](https://github.com/lino/django-recur/actions/workflows/docs.yml/badge.svg)](https://lino.github.io/django-recur/)
[![PyPI](https://img.shields.io/pypi/v/django-recur.svg)](https://pypi.org/project/django-recur/)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-recur.svg)](https://pypi.org/project/django-recur/)
[![Django Versions](https://img.shields.io/pypi/djversions/django-recur.svg)](https://pypi.org/project/django-recur/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://github.com/lino/django-recur/blob/main/LICENSE)

**`django-recur`** is the modern reimplementation of [`jazzband/django-recurrence`](https://github.com/jazzband/django-recurrence), built on **[RFC 8984 (JSCalendar)](https://datatracker.ietf.org/doc/html/rfc8984)** and **[RFC 5545 (iCalendar)](https://datatracker.ietf.org/doc/html/rfc5545)** while providing a **100% drop-in compatibility layer** for existing `django-recurrence` projects.

---

## Why `django-recur`?

`django-recurrence` served the Django ecosystem for over 15 years, wrapping `dateutil.rrule` with a partial RFC 2445 text format and a jQuery/ES3 admin widget. `django-recur` continues that lineage under independent stewardship while modernizing the entire stack:

1. **RFC 8984 (JSCalendar) Internals**: Stores and manipulates recurrence rules using the IETF standard JSON representation for calendar data (`RecurrenceRule`, `NDay`, `recurrenceRules`, `excludedRecurrenceRules`, `recurrenceOverrides`, `rscale`, `skip`).
2. **iCalendar Recurrence Interoperability**: Parses, validates, and serializes recurrence properties from RFC 5545 and RFC 2445, with structured reports for conditional and lossy conversions.
3. **100% Drop-In Compatibility (`recurrence`)**: Existing `import recurrence`, `INSTALLED_APPS = ["recurrence"]`, model fields, forms, managers, and migrations work out of the box without changing a single line of application code.
4. **Built-In Database Migration Command (`migrate_recurrences`)**: Convert stored recurrence field values to JSCalendar JSON with `--dry-run` inspection.
5. **Modern TypeScript Web Component Widget (`<django-recur-widget>`)**: Zero-jQuery Custom Element built with TypeScript and Vite, with native Django Admin light/dark theme support, inline formset `MutationObserver` support, and a legacy `window.recurrence` compatibility bridge.

---

## Quick Start

### Installation

```bash
pip install django-recur
# or with uv:
uv add django-recur
```

Add `recurrence` (and/or `django_recur`) to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "recurrence",      # Drop-in compatibility & static assets
    "django_recur",    # Modern RFC 8984 JSCalendar package
]
```

### Option A: Modern RFC 8984 JSCalendar API (`django_recur`)

```python
from datetime import datetime, timezone
from django.db import models
from django_recur.fields import JSCalendarRecurrenceField
from django_recur.rfc8984 import JSCalendarRecurrence, NDay, RecurrenceRule


class Course(models.Model):
    title = models.CharField(max_length=200)
    schedule = JSCalendarRecurrenceField()


# Create an RFC 8984 recurrence schedule programmatically
schedule = JSCalendarRecurrence(
    dtstart=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
    recurrence_rules=(
        RecurrenceRule(
            frequency="monthly",
            interval=1,
            by_day=(NDay(day="th", nth_of_period=3),),
            count=6,
        ),
    ),
)

# Serializes to canonical RFC 8984 JSCalendar JSON:
print(schedule.to_jscalendar())
# {
#   '@type': 'Event',
#   'start': '2026-01-01T09:00:00',
#   'timeZone': 'UTC',
#   'recurrenceRules': [
#     {'@type': 'RecurrenceRule', 'frequency': 'monthly', 'byDay': [{'@type': 'NDay', 'day': 'th', 'nthOfPeriod': 3}], 'count': 6}
#   ]
# }
```

### Option B: Drop-In `django-recurrence` Compatibility (`recurrence`)

```python
from django.db import models
import recurrence
from recurrence.fields import RecurrenceField


class LegacyCourse(models.Model):
    title = models.CharField(max_length=200)
    recurrences = RecurrenceField()


rule = recurrence.Rule(recurrence.WEEKLY, byday=[recurrence.MO, recurrence.WE])
pattern = recurrence.Recurrence(rrules=[rule])

# Every Rule and Recurrence object exposes its underlying RFC 8984 representation:
assert rule.to_jscalendar() == {
    "@type": "RecurrenceRule",
    "frequency": "weekly",
    "byDay": [{"@type": "NDay", "day": "mo"}, {"@type": "NDay", "day": "we"}],
}
```

---

## Migrating Existing Rules to RFC 8984

Use the included Django management command to inspect and migrate existing RFC 2445 / RFC 5545 rules stored in `RecurrenceField` columns to JSCalendar JSON:

```bash
# Preview changes without modifying the database
python manage.py migrate_recurrences --dry-run

# Migrate all RecurrenceField columns across all models to RFC 8984 JSON
python manage.py migrate_recurrences

# Migrate a specific model or field
python manage.py migrate_recurrences --model events.Course.recurrences
```

---

## Documentation

Full documentation — including the **[RFC 8984 & RFC 5545 Feature & Auto-Mapping Matrix](https://lino.github.io/django-recur/rfc-compliance-matrix/)**, migration guide, Web Component widget guide, and API reference — is published at:

👉 **[https://lino.github.io/django-recur/](https://lino.github.io/django-recur/)**

---

## License

BSD 3-Clause License. See [LICENSE](LICENSE) for details.
