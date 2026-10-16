# django-recurrence-jscalendar

[![CI](https://github.com/lino/django-recurrence-jscalendar/actions/workflows/ci.yml/badge.svg)](https://github.com/lino/django-recurrence-jscalendar/actions/workflows/ci.yml)
[![Documentation](https://github.com/lino/django-recurrence-jscalendar/actions/workflows/docs.yml/badge.svg)](https://lino.github.io/django-recurrence-jscalendar/)
[![PyPI](https://img.shields.io/pypi/v/django-recurrence-jscalendar.svg)](https://pypi.org/project/django-recurrence-jscalendar/)
[![Python Versions](https://img.shields.io/pypi/pyversions/django-recurrence-jscalendar.svg)](https://pypi.org/project/django-recurrence-jscalendar/)
[![Django Versions](https://img.shields.io/pypi/djversions/django-recurrence-jscalendar.svg)](https://pypi.org/project/django-recurrence-jscalendar/)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://github.com/lino/django-recurrence-jscalendar/blob/main/LICENSE)

**`django-recurrence-jscalendar`** is the modern reimplementation of [`jazzband/django-recurrence`](https://github.com/jazzband/django-recurrence), built on **[RFC 8984 (JSCalendar)](https://datatracker.ietf.org/doc/html/rfc8984)** and **[RFC 5545 (iCalendar)](https://datatracker.ietf.org/doc/html/rfc5545)** while providing a **100% drop-in compatibility layer** for existing `django-recurrence` projects.

---

## Why `django-recurrence-jscalendar`?

`django-recurrence` served the Django ecosystem for over 15 years, wrapping `dateutil.rrule` with a partial RFC 2445 text format and a jQuery/ES3 admin widget. `django-recurrence-jscalendar` continues that lineage under independent stewardship while modernizing the entire stack:

1. **RFC 8984 (JSCalendar) Internals**: Stores and manipulates recurrence rules using the IETF standard JSON representation for calendar data (`RecurrenceRule`, `NDay`, `recurrenceRules`, `excludedRecurrenceRules`, `recurrenceOverrides`, `rscale`, `skip`).
2. **Full RFC 5545 Compliance & Bidirectional Mapping**: Seamlessly parses, validates, and serializes RFC 5545 / RFC 2445 (`RRULE`, `EXRULE`, `RDATE`, `EXDATE`, `DTSTART`, `DTEND`) and provides structured conversion reports detailing lossless vs. lossy mappings.
3. **100% Drop-In Compatibility (`recurrence`)**: Existing `import recurrence`, `INSTALLED_APPS = ["recurrence"]`, model fields, forms, managers, and migrations work out of the box without changing a single line of application code.
4. **Built-In Database Migration Command (`migrate_recurrences`)**: Upgrade existing RFC 2445/5545 database columns and legacy relational tables (`recurrence.models.Recurrence`) to RFC 8984 JSCalendar JSON with `--dry-run` inspection.
5. **Modern TypeScript Web Component Widget (`<dj-recurrence-widget>`)**: Zero-jQuery Custom Element built with TypeScript and Vite, with native Django Admin light/dark theme support, inline formset `MutationObserver` support, and a legacy `window.recurrence` compatibility bridge.

---

## Quick Start

### Installation

```bash
pip install django-recurrence-jscalendar
# or with uv:
uv add django-recurrence-jscalendar
```

Add `recurrence` (and/or `dj_recurrence`) to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "recurrence",      # Drop-in compatibility & static assets
    "dj_recurrence",   # Modern RFC 8984 JSCalendar package
]
```

### Option A: Modern RFC 8984 JSCalendar API (`dj_recurrence`)

```python
from datetime import datetime, timezone
from django.db import models
from dj_recurrence.fields import JSCalendarRecurrenceField
from dj_recurrence.rfc8984 import JSCalendarRecurrence, NDay, RecurrenceRule


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
#   'start': '2026-01-01T09:00:00Z',
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

Use the included Django management command to inspect and migrate existing RFC 2445 / RFC 5545 rules stored in `RecurrenceField` columns (or legacy `recurrence.models.Recurrence` tables) to RFC 8984 JSCalendar JSON:

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

Full documentation — including the **[RFC 8984 & RFC 5545 Feature & Auto-Mapping Matrix](https://lino.github.io/django-recurrence-jscalendar/rfc-compliance-matrix/)**, migration guide, Web Component widget guide, and API reference — is published at:

👉 **[https://lino.github.io/django-recurrence-jscalendar/](https://lino.github.io/django-recurrence-jscalendar/)**

---

## License

BSD 3-Clause License. See [LICENSE](LICENSE) for details.
