"""Drop-in ``RecurrenceField`` model field supporting both RFC 5545 and RFC 8984."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django.db.models import fields

import recurrence
from django_recur.rfc8984 import JSCalendarRecurrence
from recurrence import forms
from recurrence import settings as recurrence_settings
from recurrence.compat import Creator


class RecurrenceField(fields.Field):
    """
    Model field that stores a ``recurrence.base.Recurrence`` in the database.

    Reads both RFC 5545 / RFC 2445 strings and RFC 8984 JSCalendar JSON strings/dicts
    transparently. Writes according to ``storage_format`` or ``settings.RECURRENCE_STORAGE_FORMAT``.
    """

    def __init__(
        self,
        include_dtstart: bool = True,
        storage_format: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.include_dtstart = include_dtstart
        self.storage_format = storage_format
        super().__init__(**kwargs)

    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()
        if not self.include_dtstart:
            kwargs["include_dtstart"] = self.include_dtstart
        if self.storage_format is not None:
            kwargs["storage_format"] = self.storage_format
        return name, path, args, kwargs

    def get_internal_type(self) -> str:
        return "TextField"

    def to_python(self, value: Any) -> recurrence.Recurrence | None:
        if value is None or isinstance(value, recurrence.Recurrence):
            return value
        if isinstance(value, JSCalendarRecurrence):
            return recurrence.Recurrence.from_jscalendar(
                value, include_dtstart=self.include_dtstart
            )
        if isinstance(value, Mapping):
            return recurrence.Recurrence.from_jscalendar(
                value, include_dtstart=self.include_dtstart
            )
        value_str = super().to_python(value) or ""
        return recurrence.deserialize(value_str, self.include_dtstart)

    def from_db_value(self, value: Any, *args: Any, **kwargs: Any) -> recurrence.Recurrence | None:
        return self.to_python(value)

    def get_prep_value(self, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            fmt = self.storage_format or recurrence_settings.storage_format()
            return recurrence.serialize(value, output_format=fmt)
        return value

    def contribute_to_class(self, cls: Any, *args: Any, **kwargs: Any) -> None:
        super().contribute_to_class(cls, *args, **kwargs)
        setattr(cls, self.name, Creator(self))

    def value_to_string(self, obj: Any) -> str:
        return self.get_prep_value(self.value_from_object(obj)) or ""

    def formfield(self, **kwargs: Any) -> Any:
        defaults: dict[str, Any] = {
            "form_class": forms.RecurrenceField,
            "widget": forms.RecurrenceWidget,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
