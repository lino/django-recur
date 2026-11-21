# Installation

## Requirements

- **Python**: 3.10 or later
- **Django**: Install Django 6.1 on Python 3.12 or later, or Django 5.2 LTS on Python 3.10 or 3.11. The package also supports existing Django 5.0 and 5.1 deployments.
- **python-dateutil**: 2.8.2 or later

## Installing the Package

Install `django-recur` using `uv` (recommended) or `pip`:

```bash
uv add django-recur
```

or with `pip`:

```bash
pip install django-recur
```

> **Note:** If you are migrating from `django-recurrence`, uninstall the legacy package first so the `recurrence` module namespace is provided by `django-recur`:
>
> ```bash
> pip uninstall django-recurrence
> pip install django-recur
> ```

## Configuring `INSTALLED_APPS`

Add both `recurrence` (for static assets, locales, and drop-in compatibility) and `django_recur` (for the RFC 8984 management commands and native JSCalendar integration) to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "recurrence",
    "django_recur",
]
```

## Optional Settings

All legacy `RECURRENCE_*` settings continue to work as expected, along with new settings for controlling default storage serialization:

| Setting | Default | Description |
| --- | --- | --- |
| `RECURRENCE_STORAGE_FORMAT` | `"rfc5545"` | Default database serialization format for `recurrence.fields.RecurrenceField`: `"rfc5545"` (RFC 5545 text) or `"rfc8984"` (RFC 8984 JSCalendar JSON string). Reading always accepts both formats automatically. |
| `RECURRENCE_DEFAULT_LIMIT` | `None` | Optional integer cap on unbounded occurrence expansion when no `dtend` or `before` bound is supplied. |
| `RECURRENCE_USE_TZ` | `settings.USE_TZ` | Controls timezone normalization during occurrence expansion. |
