"""
Drop-in form fields and widgets for ``recurrence``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

import recurrence
from dj_recurrence.widgets import (
    RecurrenceWidget,
    find_recurrence_i18n_js_catalog,
)
from recurrence import exceptions


class RecurrenceField(forms.CharField):
    """
    A form Field that accepts recurrence parameters in either RFC 5545 / RFC 2445
    or RFC 8984 (JSCalendar) format and cleans them into ``recurrence.Recurrence`` objects.
    """

    widget = RecurrenceWidget
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
        frequencies: Sequence[int] | None = None,
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
            self.frequencies = frequencies
        else:
            self.frequencies = (
                recurrence.YEARLY,
                recurrence.MONTHLY,
                recurrence.WEEKLY,
                recurrence.DAILY,
                recurrence.HOURLY,
                recurrence.MINUTELY,
                recurrence.SECONDLY,
            )
        super().__init__(*args, **kwargs)

    def clean(self, value: Any) -> recurrence.Recurrence | None:
        try:
            recurrence_obj = recurrence.deserialize(value)
        except exceptions.DeserializationError as error:
            raise forms.ValidationError(error.args[0]) from error
        except TypeError:
            return None

        if not self.accept_dtstart:
            recurrence_obj.dtstart = None
        if not self.accept_dtend:
            recurrence_obj.dtend = None

        if self.max_rrules is not None and len(recurrence_obj.rrules) > self.max_rrules:
            raise forms.ValidationError(
                self.error_messages["max_rrules_exceeded"] % {"limit": self.max_rrules}
            )
        if self.max_exrules is not None and len(recurrence_obj.exrules) > self.max_exrules:
            raise forms.ValidationError(
                self.error_messages["max_exrules_exceeded"] % {"limit": self.max_exrules}
            )
        if self.max_rdates is not None and len(recurrence_obj.rdates) > self.max_rdates:
            raise forms.ValidationError(
                self.error_messages["max_rdates_exceeded"] % {"limit": self.max_rdates}
            )
        if self.max_exdates is not None and len(recurrence_obj.exdates) > self.max_exdates:
            raise forms.ValidationError(
                self.error_messages["max_exdates_exceeded"] % {"limit": self.max_exdates}
            )

        for rrule in recurrence_obj.rrules:
            if rrule.freq not in self.frequencies:
                raise forms.ValidationError(self.error_messages["invalid_frequency"])
        for exrule in recurrence_obj.exrules:
            if exrule.freq not in self.frequencies:
                raise forms.ValidationError(self.error_messages["invalid_frequency"])

        if (
            self.required
            and not recurrence_obj.rrules
            and not recurrence_obj.rdates
            and not recurrence_obj.exdates
            and not recurrence_obj.exrules
        ):
            raise forms.ValidationError(self.error_messages["recurrence_required"])

        return recurrence_obj


__all__ = [
    "RecurrenceField",
    "RecurrenceWidget",
    "find_recurrence_i18n_js_catalog",
]
