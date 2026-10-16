"""Django AppConfig for dj_recurrence."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjRecurrenceConfig(AppConfig):
    name = "dj_recurrence"
    verbose_name = _("Recurrence (JSCalendar RFC 8984)")
    default_auto_field = "django.db.models.BigAutoField"
