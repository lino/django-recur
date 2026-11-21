# Changelog

All notable changes to `django-recur` are documented on this page.

## [2.0.0] - 2026-10-15

### Added

- **RFC 8984 (JSCalendar) Core Engine (`django_recur`)**:
  - Full implementation of RFC 8984 §4.3 (`JSCalendarRecurrence`, `RecurrenceRule`, `NDay`, `RecurrenceOverride`, `Frequency`, `DayOfWeek`, `Skip`).
  - Support for RFC 8984 `skip="omit" | "backward" | "forward"` occurrence shifting (e.g., leap-day Feb 29 handling in non-leap years) and `rscale`.
  - Native `JSCalendarRecurrenceField` (subclassing `django.db.models.JSONField`) and `JSCalendarRecurrenceFormField`.
- **Bidirectional RFC 8984 ↔ RFC 5545 Converter & Audit Matrix (`django_recur.rfc5545`)**:
  - `FEATURE_MATRIX`, `ConversionIssue`, and `ConversionReport` for programmatic inspection of lossless, conditional, and lossy mappings between RFC 8984 and RFC 5545.
  - `convert_jscalendar_to_icalendar_with_report()` and `convert_icalendar_to_jscalendar_with_report()` with `strict=True` mode.
- **Database Migration Management Command (`migrate_recurrences`)**:
  - Added `python manage.py migrate_recurrences` (available in both `django_recur` and `recurrence`) supporting `--dry-run`, `--model`, `--target-format`, `--batch-size`, `--include-defaults`, `--strict`, and `--json`.
- **TypeScript + Vite Web Component Widget (`<django-recur-widget>`)**:
  - Built a modern Custom Element (`<django-recur-widget>`) with Shadow DOM encapsulation, dark/light theme support, live human-readable summary, dual RFC 8984 / RFC 5545 serialization, and legacy `window.recurrence.widget.Widget` bridge.
- **100% Drop-In `django-recurrence` Compatibility (`recurrence`)**:
  - Preserved all classes, constants, methods, model fields, form fields, and relational models from `jazzband/django-recurrence` while delegating internally to the RFC 8984 engine.
