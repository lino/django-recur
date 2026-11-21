# Installation

## Overview

**What you will learn:**

- How to install `django-recur` with `uv` or `pip`.
- How to register both namespaces in Django's `INSTALLED_APPS`.
- Which optional Django settings control storage format and timezone handling.

Install `django-recur` to add RFC 8984 (JSCalendar) recurrence fields and the `<django-recur-widget>` form widget to your Django project.

## Prerequisites

- **Python**: 3.10 or later.
- **Django**: 6.1 on Python 3.12+, or 5.2 LTS on Python 3.10–3.11 (Django 5.0 and 5.1 are also supported).
- **python-dateutil**: 2.8.2 or later (installed automatically).

## Steps

1. Uninstall `django-recurrence` first if you are upgrading an existing project. This prevents namespace conflicts on the `recurrence` module.

   ```bash
   pip uninstall django-recurrence
   ```

2. Install `django-recur` using `uv` (recommended) or `pip`:

   ```bash
   uv add django-recur
   ```

   Or with `pip`:

   ```bash
   pip install django-recur
   ```

3. Add both `"recurrence"` and `"django_recur"` to `INSTALLED_APPS` in `settings.py`. `"recurrence"` provides static assets, locales, and drop-in compatibility; `"django_recur"` provides native JSCalendar integration and management commands.

   ```python
   INSTALLED_APPS = [
       # ...
       "recurrence",
       "django_recur",
   ]
   ```

4. Collect static files if you serve assets through Django's staticfiles pipeline:

   ```bash
   python manage.py collectstatic
   ```

## Expected Outcome

Verify that Django discovers both packages and the `migrate_recurrences` management command:

```bash
python manage.py migrate_recurrences --help
```

The command prints its usage summary and available flags without import errors.

## Optional Settings

All legacy `RECURRENCE_*` settings continue to work alongside the storage format setting:

| Setting | Default | Description |
| --- | --- | --- |
| `RECURRENCE_STORAGE_FORMAT` | `"rfc5545"` | Default write format for `recurrence.fields.RecurrenceField`: `"rfc5545"` (iCalendar text) or `"rfc8984"` (JSCalendar JSON string). Reading always accepts both formats automatically. |
| `RECURRENCE_DEFAULT_LIMIT` | `None` | Optional integer cap on unbounded occurrence expansion when no `dtend` or `before` bound is supplied. |
| `RECURRENCE_USE_TZ` | `settings.USE_TZ` | Controls timezone awareness when deserializing datetimes. |

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ImportError` for `django_recur` or missing `RecurrenceField` methods | Legacy `django-recurrence` is still installed in the same environment. | Run `pip uninstall django-recurrence` and reinstall `django-recur`. |
| `<django-recur-widget>` renders as a plain `<textarea>` | Static files were not collected or `{{ form.media }}` is missing from the template. | Add `{{ form.media }}` to your template and run `python manage.py collectstatic`. |
| `Unknown command: 'migrate_recurrences'` | Neither `"django_recur"` nor `"recurrence"` is listed in `INSTALLED_APPS`. | Add both apps to `INSTALLED_APPS` in `settings.py`. |
