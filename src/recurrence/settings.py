"""
Settings for django-recur.

- ``RECURRENCE_USE_TZ``: Determines if a datetime deserialized from RFC 5545 or
  RFC 8984 text is returned as a timezone-aware datetime or naive datetime.
  Defaults to ``settings.USE_TZ``.
- ``RECURRENCE_STORAGE_FORMAT``: Determines the default database serialization
  format for ``recurrence.fields.RecurrenceField`` (``"rfc5545"`` or ``"rfc8984"``).
  Defaults to ``"rfc5545"`` for drop-in backwards compatibility; reading from
  the database always accepts both RFC 5545 and RFC 8984 transparently.
"""

from __future__ import annotations

from django.conf import settings


def deserialize_tz() -> bool:
    try:
        return bool(settings.RECURRENCE_USE_TZ)
    except AttributeError:
        return bool(settings.USE_TZ)


def storage_format() -> str:
    return str(getattr(settings, "RECURRENCE_STORAGE_FORMAT", "rfc5545")).lower()
