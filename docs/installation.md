# Installation

## Requirements

- **Python**: 3.11, 3.12, 3.13, or 3.14+
- **Django**: 4.2 LTS, 5.1, or 5.2+
- **python-dateutil**: >= 2.9.0

## Installing the Package

Install `django-recurrence-jscalendar` using `uv` (recommended) or `pip`:

```bash
uv add django-recurrence-jscalendar
```

or with `pip`:

```bash
pip install django-recurrence-jscalendar
```

> **Note:** If you are migrating from `django-recurrence`, uninstall the legacy package first so the `recurrence` module namespace is provided by `django-recurrence-jscalendar`:
>
> ```bash
> pip uninstall django-recurrence
> pip install django-recurrence-jscalendar
> ```

## Configuring `INSTALLED_APPS`

Add both `recurrence` (for static assets, locales, and drop-in compatibility) and `dj_recurrence` (for the RFC 8984 management commands and native JSCalendar integration) to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    "recurrence",
    "dj_recurrence",
]
```

## Optional Settings

All legacy `RECURRENCE_*` settings continue to work as expected, along with new settings for controlling default storage serialization:

| Setting | Default | Description |
| --- | --- | --- |
| `RECURRENCE_STORAGE_FORMAT` | `"rfc5545"` | Default database serialization format for `recurrence.fields.RecurrenceField`: `"rfc5545"` (RFC 5545 text) or `"rfc8984"` (RFC 8984 JSCalendar JSON string). Reading always accepts both formats automatically. |
| `RECURRENCE_DEFAULT_LIMIT` | `None` | Optional integer cap on unbounded occurrence expansion when no `dtend` or `before` bound is supplied. |
| `RECURRENCE_USE_TZ` | `settings.USE_TZ` | Controls timezone normalization during occurrence expansion. |
