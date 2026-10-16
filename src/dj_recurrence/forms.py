"""
Django form fields for RFC 8984 JSCalendar and RFC 5545 recurrences.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from dj_recurrence import exceptions
from dj_recurrence.rfc5545 import deserialize_any
from dj_recurrence.rfc8984 import Frequency, JSCalendarRecurrence
from dj_recurrence.widgets import JSCalendarRecurrenceWidget


class JSCalendarRecurrenceFormField(forms.CharField):
    """
    Form field that accepts either RFC 8984 JSCalendar JSON or RFC 5545 iCalendar
    input and cleans it into a ``JSCalendarRecurrence`` instance.
    """

    widget = JSCalendarRecurrenceWidget
    default_error_messages = {
        "invalid_frequency": _("Invalid frequency."),
        "max_rrules_exceeded": _("Max rules exceeded. The limit is %(limit)s"),
        "max_exrules_exceeded": _("Max exclusion rules exceeded. The limit is %(limit)s"),
        "max_rdates_exceeded": _("Max dates exceeded. The limit is %(limit)s"),
        "max_exdates_exceeded": _("Max exclusion dates exceeded. The limit is %(limit)s"),
        "recurrence_required": _("This field is required. Set either a recurrence rule or date."),
    }

    def __init__(
        self,
        frequencies: Sequence[str | int | Frequency] | None = None,
        accept_dtstart: bool = True,
        accept_dtend: bool = True,
        max_rrules: int | None = None,
        max_exrules: int | None = None,
        max_rdates: int | None = None,
        max_exdates: int | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.accept_dtstart = accept_dtstart
        self.accept_dtend = accept_dtend
        self.max_rrules = max_rrules
        self.max_exrules = max_exrules
        self.max_rdates = max_rdates
        self.max_exdates = max_exdates

        if frequencies is not None:
            normalized_freqs: list[str] = []
            for f in frequencies:
                if isinstance(f, Frequency):
                    normalized_freqs.append(f.value)
                elif isinstance(f, int) and not isinstance(f, bool):
                    normalized_freqs.append(Frequency.from_int(f).value)
                else:
                    normalized_freqs.append(str(f).lower())
            self.frequencies: tuple[str, ...] = tuple(normalized_freqs)
        else:
            self.frequencies = tuple(f.value for f in Frequency)

        super().__init__(*args, **kwargs)

    def clean(self, value: Any) -> JSCalendarRecurrence | None:
        if value is None:
            if self.required:
                raise forms.ValidationError(self.error_messages["required"], code="required")
            return None

        try:
            rec_obj = deserialize_any(value)
        except exceptions.DeserializationError as error:
            raise forms.ValidationError(error.args[0]) from error
        except TypeError:
            return None

        if not self.accept_dtstart:
            rec_obj.dtstart = None
        if not self.accept_dtend:
            rec_obj.dtend = None

        if self.max_rrules is not None and len(rec_obj.rrules) > self.max_rrules:
            raise forms.ValidationError(
                self.error_messages["max_rrules_exceeded"] % {"limit": self.max_rrules}
            )
        if self.max_exrules is not None and len(rec_obj.exrules) > self.max_exrules:
            raise forms.ValidationError(
                self.error_messages["max_exrules_exceeded"] % {"limit": self.max_exrules}
            )
        if self.max_rdates is not None and len(rec_obj.rdates) > self.max_rdates:
            raise forms.ValidationError(
                self.error_messages["max_rdates_exceeded"] % {"limit": self.max_rdates}
            )
        if self.max_exdates is not None and len(rec_obj.exdates) > self.max_exdates:
            raise forms.ValidationError(
                self.error_messages["max_exdates_exceeded"] % {"limit": self.max_exdates}
            )

        for rrule in rec_obj.rrules:
            if str(rrule.frequency).lower() not in self.frequencies:
                raise forms.ValidationError(self.error_messages["invalid_frequency"])
        for exrule in rec_obj.exrules:
            if str(exrule.frequency).lower() not in self.frequencies:
                raise forms.ValidationError(self.error_messages["invalid_frequency"])

        if (
            self.required
            and not rec_obj.rrules
            and not rec_obj.rdates
            and not rec_obj.exdates
            and not rec_obj.exrules
        ):
            raise forms.ValidationError(self.error_messages["recurrence_required"])

        return rec_obj
