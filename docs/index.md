# django-recur

**`django-recur`** is a modern reimplementation of [`jazzband/django-recurrence`](https://github.com/jazzband/django-recurrence) for Django, including Django 6.1 on Python 3.12 or later.

To mark continuity with `django-recurrence` while signaling the architectural shift from legacy RFC 2445 strings to structured JSON calendar models, this project is published at [`lino/django-recur`](https://github.com/lino/django-recur) and ships **two co-existing namespaces** in a single distribution:

1. **`django_recur`**: The native **RFC 8984 (JSCalendar)** engine, `JSCalendarRecurrenceField` (backed by `JSONField`), bidirectional **RFC 8984 ↔ RFC 5545** converter with conversion audit reports, and the `migrate_recurrences` management command.
2. **`recurrence`**: A **100% drop-in compatible** layer for `django-recurrence` that preserves every class, constant, method (`occurrences()`, `between()`, `after()`, `before()`, `count()`), form field, and migration path—while delegating occurrence expansion and validation to the RFC 8984 engine under the hood.

---

## Key Highlights

- **RFC 8984 (JSCalendar) Core Engine**: First-class dataclasses (`JSCalendarRecurrence`, `RecurrenceRule`, `NDay`, `RecurrenceOverride`, `Frequency`, `DayOfWeek`, `Skip`) implementing RFC 8984 §4.3 validation and occurrence expansion (including `rscale` and `skip="omit" | "backward" | "forward"`).
- **iCalendar Interoperability** converts recurrence properties and reports cases where conversion loses information. See the [RFC 8984 & RFC 5545 Feature Matrix](rfc-compliance-matrix.md).
- **Drop-In `django-recurrence` Replacement**: Existing code importing `from recurrence.fields import RecurrenceField` or `import recurrence` works unmodified. `RecurrenceField.to_python()` transparently parses both legacy RFC 2445/5545 strings and new RFC 8984 JSCalendar JSON payloads.
- **Zero-Downtime Database Migration Command**: Run `python manage.py migrate_recurrences` (with `--dry-run`, `--model`, `--batch-size`, `--strict`, and `--json`) to inspect and migrate all stored recurrence columns to RFC 8984 JSCalendar JSON.
- **Modern TypeScript Web Component Widget (`<django-recur-widget>`)**: Built with TypeScript and Vite using Custom Elements v1 and Shadow DOM, supporting Django Admin dark/light themes, dynamic inline formsets (`formset:added`), and both RFC 8984 JSON and RFC 5545 `RRULE` output modes.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Django Application Layer                         │
├───────────────────────────────────┬─────────────────────────────────────┤
│   Drop-In Compatibility Layer     │       Modern JSCalendar Layer       │
│          (recurrence.*)           │          (django_recur.*)           │
│  • RecurrenceField (Text/JSON)    │  • JSCalendarRecurrenceField (JSON) │
│  • Recurrence, Rule, Weekday      │  • JSCalendarRecurrence, NDay       │
│  • serialize() / deserialize()    │  • RecurrenceRule, Override         │
├───────────────────────────────────┴─────────────────────────────────────┤
│              Bidirectional RFC 8984 ↔ RFC 5545 Bridge                   │
│  • convert_jscalendar_to_icalendar_with_report()                        │
│  • convert_icalendar_to_jscalendar_with_report()                        │
│  • FEATURE_MATRIX & ConversionReport                                    │
├─────────────────────────────────────────────────────────────────────────┤
│         <django-recur-widget> TypeScript Web Component (Vite)           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Next Steps

- [Installation](installation.md): Install `django-recur` with `uv` or `pip`.
- [Quickstart](getting-started.md): Use either the drop-in `recurrence` API or the native `django_recur` API.
- [RFC 8984 & RFC 5545 Matrix](rfc-compliance-matrix.md): Inspect the full feature and auto-mapping matrix between RFC 8984 and RFC 5545.
- [Migration Guide](migration-guide.md): Migrate existing `django-recurrence` projects and databases using `migrate_recurrences`.
- [TypeScript Web Component Widget](widget.md): Customize `<django-recur-widget>` and build frontend assets.
