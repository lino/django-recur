"""
Tests for JSCalendarRecurrenceField, JSCalendarRecurrenceFormField,
RecurrenceWidget (<django-recur-widget>), and dual-format storage.
"""

from __future__ import annotations

import html
import json
from datetime import datetime

import pytest
from django import forms
from django.test import override_settings

import recurrence
from django_recur.fields import JSCalendarCreator, JSCalendarRecurrenceField
from django_recur.forms import JSCalendarRecurrenceFormField
from django_recur.rfc8984 import Frequency, JSCalendarRecurrence, NDay, RecurrenceRule
from django_recur.widgets import (
    JSCalendarRecurrenceWidget,
    RecurrenceWidget,
    find_recurrence_i18n_js_catalog,
)
from tests.models import EventWithJSCalendarStorage, NativeJSCalendarEvent


@pytest.mark.django_db
def test_native_jscalendar_recurrence_field_crud():
    # Descriptor access on class returns JSCalendarCreator
    assert isinstance(NativeJSCalendarEvent.recurs, JSCalendarCreator)

    # 2026-02-02 is a Monday
    schedule = JSCalendarRecurrence(
        start=datetime(2026, 2, 2, 10, 0, 0),
        recurrence_rules=[
            RecurrenceRule(
                frequency=Frequency.WEEKLY,
                interval=1,
                by_day=[NDay("mo"), NDay("we")],
                count=4,
            )
        ],
    )

    event = NativeJSCalendarEvent.objects.create(title="Standup", recurs=schedule)
    event.refresh_from_db()

    assert isinstance(event.recurs, JSCalendarRecurrence)
    assert event.recurs == schedule
    assert len(list(event.recurs.occurrences())) == 4

    field = NativeJSCalendarEvent._meta.get_field("recurs")
    assert '"frequency": "weekly"' in field.value_to_string(event)

    # Assigning a RecurrenceRule directly
    event.recurs = RecurrenceRule(frequency=Frequency.DAILY, count=2)
    event.save()
    event.refresh_from_db()
    assert isinstance(event.recurs, JSCalendarRecurrence)
    assert event.recurs.recurrence_rules[0].count == 2

    # Assigning a dict directly
    event.recurs = {
        "@type": "Event",
        "recurrenceRules": [{"@type": "RecurrenceRule", "frequency": "hourly", "count": 3}],
    }
    event.save()
    event.refresh_from_db()
    assert event.recurs.recurrence_rules[0].frequency == "hourly"

    # Assigning an RFC 5545 string directly
    event.recurs = "RRULE:FREQ=DAILY;COUNT=3"
    event.save()
    event.refresh_from_db()
    assert isinstance(event.recurs, JSCalendarRecurrence)
    assert event.recurs.recurrence_rules[0].frequency == "daily"
    assert event.recurs.recurrence_rules[0].count == 3

    # Assigning an empty string
    event.recurs = ""
    event.save()
    event.refresh_from_db()
    assert event.recurs == JSCalendarRecurrence()

    # Assigning a legacy recurrence.Recurrence object
    legacy_rec = recurrence.Recurrence(
        rrules=[recurrence.Rule(recurrence.MONTHLY, bymonthday=[15], count=2)]
    )
    event.recurs = legacy_rec
    event.save()
    event.refresh_from_db()
    assert event.recurs.recurrence_rules[0].by_month_day == (15,)

    # Direct get_prep_value checks for all supported input types
    assert field.get_prep_value(None) is None
    assert field.get_prep_value(RecurrenceRule(frequency="daily")) is not None
    assert field.get_prep_value(legacy_rec) is not None
    assert field.get_prep_value("RRULE:FREQ=DAILY") is not None
    assert (
        field.get_prep_value({"@type": "Event", "recurrenceRules": [{"frequency": "daily"}]})
        is not None
    )

    # Null assignment
    event.recurs = None
    event.save()
    event.refresh_from_db()
    assert event.recurs is None
    assert field.value_to_string(event) == ""


@pytest.mark.django_db
def test_legacy_recurrence_field_with_rfc8984_storage_format():
    pattern = recurrence.Recurrence(
        dtstart=datetime(2026, 1, 1, 0, 0, 0),
        rrules=[recurrence.Rule(recurrence.WEEKLY, byday=[recurrence.MO, recurrence.FR], count=4)],
    )
    obj = EventWithJSCalendarStorage.objects.create(recurs=pattern)

    field = EventWithJSCalendarStorage._meta.get_field("recurs")
    name, _path, _args, kwargs = field.deconstruct()
    assert name == "recurs"
    assert kwargs["storage_format"] == "rfc8984"

    serialized_str = field.value_to_string(obj)
    parsed_json = json.loads(serialized_str)
    assert parsed_json["@type"] == "Event"
    assert parsed_json["recurrenceRules"][0]["frequency"] == "weekly"

    obj.refresh_from_db()
    assert isinstance(obj.recurs, recurrence.Recurrence)
    assert obj.recurs == pattern

    # Assigning JSCalendarRecurrence or dict to legacy RecurrenceField
    obj.recurs = JSCalendarRecurrence(recurrence_rules=[RecurrenceRule(frequency="daily", count=2)])
    assert isinstance(obj.recurs, recurrence.Recurrence)
    obj.recurs = {"@type": "Event", "recurrenceRules": [{"frequency": "weekly"}]}
    assert isinstance(obj.recurs, recurrence.Recurrence)


def test_jscalendar_field_deconstruct_and_formfield():
    field = JSCalendarRecurrenceField(include_dtstart=False)
    _name, _path, _args, kwargs = field.deconstruct()
    assert kwargs["include_dtstart"] is False

    form_field = field.formfield()
    assert isinstance(form_field, JSCalendarRecurrenceFormField)
    assert isinstance(form_field.widget, JSCalendarRecurrenceWidget)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        "RRULE:FREQ=DAILY;COUNT=2",
        '{"@type":"Event","recurrenceRules":[{"frequency":"daily","count":2}]}',
    ],
)
def test_native_model_form_save_and_json_lookups(payload):
    form_class = forms.modelform_factory(NativeJSCalendarEvent, fields=("title", "recurs"))
    form = form_class(data={"title": "Standup", "recurs": payload})
    assert form.is_valid(), form.errors
    event = form.save()

    deferred = NativeJSCalendarEvent.objects.only("title").get(pk=event.pk)
    assert deferred.recurs.recurrence_rules[0].count == 2
    assert (
        NativeJSCalendarEvent.objects.values_list(
            "recurs__recurrenceRules__0__count", flat=True
        ).get(pk=event.pk)
        == 2
    )
    assert NativeJSCalendarEvent.objects.get(recurs__recurrenceRules__0__count=2).pk == event.pk


def test_jscalendar_form_field_validation():
    form_field = JSCalendarRecurrenceFormField(
        frequencies=[Frequency.WEEKLY, recurrence.DAILY, "monthly"],
        accept_dtstart=False,
        accept_dtend=False,
        max_rrules=1,
        max_exrules=1,
        max_rdates=1,
        max_exdates=1,
    )

    # Accepts RFC 8984 JSON and strips dtstart/dtend when accept_dtstart=False
    cleaned_json = form_field.clean(
        json.dumps(
            {
                "@type": "Event",
                "start": "2026-01-01T09:00:00Z",
                "dtend": "2026-02-01T09:00:00Z",
                "recurrenceRules": [{"@type": "RecurrenceRule", "frequency": "weekly", "count": 2}],
            }
        )
    )
    assert isinstance(cleaned_json, JSCalendarRecurrence)
    assert cleaned_json.dtstart is None
    assert cleaned_json.dtend is None
    assert cleaned_json.recurrence_rules[0].frequency == "weekly"

    # Accepts RFC 5545 text
    cleaned_ical = form_field.clean("RRULE:FREQ=DAILY;COUNT=5")
    assert isinstance(cleaned_ical, JSCalendarRecurrence)
    assert cleaned_ical.recurrence_rules[0].frequency == "daily"

    # Rejects None when required=True
    with pytest.raises(forms.ValidationError):
        form_field.clean(None)

    # Allows None when required=False
    optional_field = JSCalendarRecurrenceFormField(required=False)
    assert optional_field.clean(None) is None

    # Rejects malformed input
    with pytest.raises(forms.ValidationError):
        form_field.clean("RRULE:INVALID_SYNTAX")

    # Rejects disallowed frequency in rrules and exrules
    with pytest.raises(forms.ValidationError) as exc_info:
        form_field.clean("RRULE:FREQ=YEARLY")
    assert exc_info.value.messages[0] == "Invalid frequency."

    with pytest.raises(forms.ValidationError) as exc_info:
        form_field.clean("EXRULE:FREQ=YEARLY")
    assert exc_info.value.messages[0] == "Invalid frequency."

    # Rejects max_rrules, max_exrules, max_rdates, max_exdates exceeded
    with pytest.raises(forms.ValidationError):
        form_field.clean("RRULE:FREQ=DAILY\nRRULE:FREQ=WEEKLY")

    with pytest.raises(forms.ValidationError):
        form_field.clean("EXRULE:FREQ=DAILY\nEXRULE:FREQ=WEEKLY")

    with pytest.raises(forms.ValidationError):
        form_field.clean("RDATE:20260101T000000Z,20260102T000000Z")

    with pytest.raises(forms.ValidationError):
        form_field.clean("EXDATE:20260101T000000Z,20260102T000000Z")

    # Rejects empty recurrence when required=True
    with pytest.raises(forms.ValidationError):
        form_field.clean(json.dumps({"@type": "Event"}))


@override_settings(DEBUG=True)
def test_web_component_widget_rendering_and_media():
    widget_5545 = RecurrenceWidget()
    assert widget_5545.format_value(None) == ""
    assert widget_5545.format_value("") == ""
    assert widget_5545.format_value("RRULE:FREQ=DAILY") == "RRULE:FREQ=DAILY"
    assert widget_5545.format_value(RecurrenceRule(frequency="daily")) == "RRULE:FREQ=DAILY"
    assert widget_5545.format_value({"frequency": "daily"}) == '{"frequency": "daily"}'

    rendered_5545 = widget_5545.render(
        "recurs",
        JSCalendarRecurrence(recurrence_rules=[RecurrenceRule(frequency="weekly")]),
        attrs={"id": "id_recurs"},
    )
    assert "<django-recur-widget" in rendered_5545
    assert 'data-output-format="rfc5545"' in rendered_5545
    assert "RRULE:FREQ=WEEKLY" in rendered_5545

    widget_8984 = JSCalendarRecurrenceWidget(show_preview=True)
    assert '"frequency": "weekly"' in (
        widget_8984.format_value(
            JSCalendarRecurrence(recurrence_rules=[RecurrenceRule(frequency="weekly")])
        )
        or ""
    )
    assert '"frequency": "weekly"' in (
        widget_8984.format_value(recurrence.Rule(recurrence.WEEKLY)) or ""
    )

    rendered_8984 = widget_8984.render(
        "schedule",
        RecurrenceRule(frequency="daily", count=3),
        attrs={"id": "id_schedule"},
    )
    unescaped = html.unescape(rendered_8984)
    assert "<django-recur-widget" in unescaped
    assert 'data-output-format="rfc8984"' in unescaped
    assert '"frequency": "daily"' in unescaped

    media_html = str(widget_8984.media)
    assert "recurrence-widget.js" in media_html
    assert "recurrence.css" in media_html
    assert find_recurrence_i18n_js_catalog() is None
