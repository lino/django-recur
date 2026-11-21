"""
Django model fields for storing RFC 8984 JSCalendar recurrences in JSONField or TextField.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from django.db import models
from django.db.models.fields.json import KeyTransform
from django.db.models.query_utils import DeferredAttribute

from django_recur import forms as dj_forms
from django_recur import widgets as dj_widgets
from django_recur.rfc5545 import deserialize_any
from django_recur.rfc8984 import JSCalendarRecurrence, RecurrenceRule


class JSCalendarCreator(DeferredAttribute):
    """Descriptor ensuring model attribute assignment converts values via ``to_python``."""

    def __set__(self, obj: Any, value: Any) -> None:
        obj.__dict__[self.field.attname] = self.field.to_python(value)


class JSCalendarRecurrenceField(models.JSONField):
    """
    Modern Django model field that stores recurrence rules natively as an
    RFC 8984 JSCalendar JSON structure inside a ``JSONField`` while exposing
    a ``JSCalendarRecurrence`` object in Python.
    """

    descriptor_class = JSCalendarCreator

    def __init__(self, include_dtstart: bool = True, **kwargs: Any) -> None:
        self.include_dtstart = include_dtstart
        super().__init__(**kwargs)

    def deconstruct(self) -> tuple[str, str, Sequence[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()
        if not self.include_dtstart:
            kwargs["include_dtstart"] = self.include_dtstart
        return name, path, args, kwargs

    def to_python(self, value: Any) -> JSCalendarRecurrence | None:
        if value is None or isinstance(value, JSCalendarRecurrence):
            return value
        if isinstance(value, RecurrenceRule):
            return JSCalendarRecurrence(
                recurrence_rules=[value], include_dtstart=self.include_dtstart
            )
        if hasattr(value, "to_jscalendar"):
            return JSCalendarRecurrence.from_jscalendar(
                value.to_jscalendar(), include_dtstart=self.include_dtstart
            )
        if isinstance(value, Mapping):
            return JSCalendarRecurrence.from_jscalendar(value, include_dtstart=self.include_dtstart)
        if isinstance(value, str):
            if not value:
                return JSCalendarRecurrence(include_dtstart=self.include_dtstart)
            return deserialize_any(value, include_dtstart=self.include_dtstart)
        return deserialize_any(str(value), include_dtstart=self.include_dtstart)

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        parsed = super().from_db_value(value, expression, connection)
        if isinstance(expression, KeyTransform):
            return parsed
        return self.to_python(parsed)

    def validate(self, value: Any, model_instance: models.Model | None) -> None:
        super().validate(self.get_prep_value(value), model_instance)

    def get_prep_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, JSCalendarRecurrence):
            return super().get_prep_value(value.to_jscalendar())
        if isinstance(value, RecurrenceRule):
            rec = JSCalendarRecurrence(
                recurrence_rules=[value], include_dtstart=self.include_dtstart
            )
            return super().get_prep_value(rec.to_jscalendar())
        if hasattr(value, "to_jscalendar"):
            return super().get_prep_value(value.to_jscalendar())
        if isinstance(value, str):
            parsed_rec = self.to_python(value)
            return super().get_prep_value(
                parsed_rec.to_jscalendar() if parsed_rec is not None else None
            )
        if isinstance(value, Mapping):
            mapped_rec = JSCalendarRecurrence.from_jscalendar(
                value, include_dtstart=self.include_dtstart
            )
            return super().get_prep_value(mapped_rec.to_jscalendar())
        return super().get_prep_value(value)

    def value_to_string(self, obj: models.Model) -> str:
        val = self.value_from_object(obj)
        if val is None:
            return ""
        if isinstance(val, JSCalendarRecurrence):
            return val.to_json()
        return json.dumps(self.get_prep_value(val))

    def formfield(self, **kwargs: Any) -> Any:
        defaults: dict[str, Any] = {
            "form_class": dj_forms.JSCalendarRecurrenceFormField,
            "widget": dj_widgets.JSCalendarRecurrenceWidget,
        }
        defaults.update(kwargs)
        return models.Field.formfield(self, **defaults)
