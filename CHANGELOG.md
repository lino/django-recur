# Changelog

All notable changes to `django-recurrence-jscalendar` (and historical `django-recurrence` releases prior to the fork) are documented in this file.

## 2.0.0 (2026-10-15)

**Major Release — The RFC 8984 JSCalendar Reimplementation (`django-recurrence-jscalendar`)**

`django-recurrence-jscalendar` marks both continuity with `jazzband/django-recurrence` (maintained by Lino Helms) and a clean architectural modernization around **RFC 8984 (JSCalendar)**.

### Highlights
- **RFC 8984 (JSCalendar) Core Engine (`dj_recurrence`)**:
  - Strictly typed dataclasses (`RecurrenceRule`, `NDay`, `RecurrenceOverride`, `JSCalendarRecurrence`) and enums (`Frequency`, `DayOfWeek`, `Skip`).
  - Native support for `recurrenceRules`, `excludedRecurrenceRules`, `recurrenceOverrides` (inclusions, exclusions, and instance patch objects), `rscale`, `skip` (`omit`, `backward`, `forward`), `firstDayOfWeek`, and all `by*` rules.
  - Native `JSCalendarRecurrenceField` backed by Django's `models.JSONField`.
- **RFC 5545 (iCalendar) Compliance & Bidirectional Mapping**:
  - Full parser, validator, and serializer for RFC 5545 / RFC 2445 (`DTSTART`, `DTEND`, `RRULE`, `EXRULE`, `RDATE`, `EXDATE`).
  - Bidirectional conversion between RFC 8984 and RFC 5545 with structured `ConversionReport` diagnostics (`lossless`, `warnings`, `unmapped_features`) and programmatic `FEATURE_MATRIX`.
- **100% Drop-In Compatibility with `django-recurrence` (`recurrence`)**:
  - Existing imports (`import recurrence`, `from recurrence.fields import RecurrenceField`), `INSTALLED_APPS = ["recurrence"]`, migrations, models (`Recurrence`, `Rule`, `Date`, `Param`), managers, and forms continue to work without code changes.
  - `recurrence.Rule`, `recurrence.Recurrence`, and `recurrence.Weekday` are internally backed by the RFC 8984 engine (`to_jscalendar()`, `from_jscalendar()`).
  - `recurrence.deserialize()` and `RecurrenceField` transparently read both RFC 2445/5545 text and RFC 8984 JSON payloads.
- **Database Migration Management Command**:
  - Added `python manage.py migrate_recurrences` (available under both `dj_recurrence` and `recurrence`) to migrate existing `RecurrenceField` database columns and legacy `recurrence.models.Recurrence` relational tables to RFC 8984 JSCalendar JSON (`--dry-run`, `--model`, `--from-legacy-models`, `--target-format`).
- **Modern TypeScript + Web Components Widget (`<dj-recurrence-widget>`)**:
  - Replaced the legacy ES3/jQuery widget with a dependency-free Custom Element (`<dj-recurrence-widget>`) built with TypeScript and Vite.
  - Supports Django Admin light/dark mode (`prefers-color-scheme` and Django Admin theme variables), inline formsets via `MutationObserver`, live human-readable previews, and full legacy `window.recurrence` bridge compatibility.
- **Modern Tooling, Docs & Governance**:
  - Switched build & dependency management to `uv` + `hatchling`, linting/formatting to `ruff`, type checking to `mypy`, and documentation to **Zensical** (`zensical.toml`) deployed to GitHub Pages.

---

## Historical `django-recurrence` Releases

### 1.12.1 (2024)
- Drop official support for Django versions 2.2, 3.2.
- Drop official support for Python versions 3.7, 3.8.
- Added support for `DEFAULT_AUTO_FIELD`.
- Added Arabic translation.

### 1.11.1 (2021-01-25)
- Fix reStructuredText syntax to be PyPI compliant.

### 1.11.0 (2021-01-21)
- Add Django 4.0 and Python 3.10 support.
- Fix weekday deserialization typing bug.
- Fix default `recurrence.language_code` not being set by using `en-us` for locale in frontend as the default.

### 1.10.3
- Add Hungarian localisation (#161).

### 1.10.2
- Add Hebrew localisation (#159).

### 1.10.1
- Update path to jQuery to match the one Django admin provides (#148).

### 1.10.0
- Fixes and official support for Django 2.1 and 2.2 (#143, #142).
- Remove support for Python 2.7 and 3.5, remove support for Django 2.0 (#145).
