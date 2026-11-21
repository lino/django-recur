"""Django AppConfig for django_recur."""

from __future__ import annotations

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DjangoRecurConfig(AppConfig):
    name = "django_recur"
    verbose_name = _("Recurrence (JSCalendar RFC 8984)")
    default_auto_field = "django.db.models.BigAutoField"
