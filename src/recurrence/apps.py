"""Django AppConfig for recurrence."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RecurrenceConfig(AppConfig):
    name = "recurrence"
    verbose_name = _("Django Recurrence")
    default_auto_field = "django.db.models.BigAutoField"
