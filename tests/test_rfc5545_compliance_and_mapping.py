"""
Tests for RFC 5545 compliance, the RFC 8984 <-> RFC 5545 Feature Matrix,
bidirectional conversion reports, and dateutil conversion helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import dateutil.rrule
import pytest
from django.test import override_settings
from django.utils import timezone as django_timezone

import recurrence
from django_recur import exceptions
from django_recur.rfc5545 import (
    FEATURE_MATRIX,
    convert_icalendar_to_jscalendar_with_report,
    convert_jscalendar_to_icalendar_with_report,
    deserialize_any,
)
from django_recur.rfc8984 import (
    Frequency,
    JSCalendarRecurrence,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    Skip,
)

CALENDAR_CASES = json.loads(Path(__file__).with_name("calendar_cases.json").read_text())


@override_settings(RECURRENCE_USE_TZ=True)
def test_folded_zoned_recurrence_crosses_dst_and_exdates_win():
    fixture = CALENDAR_CASES["foldedBerlin"]
    with django_timezone.override("America/New_York"):
        report = convert_icalendar_to_jscalendar_with_report(fixture["icalendar"])
        assert report.lossless
        assert report.output.to_jscalendar() == fixture["jscalendar"]
        restored = JSCalendarRecurrence.from_jscalendar(fixture["jscalendar"])
    assert [
        date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for date in restored.occurrences()
    ] == fixture["occurrencesUTC"]


@pytest.mark.parametrize("case", CALENDAR_CASES["localUntil"], ids=lambda case: case["description"])
@override_settings(RECURRENCE_USE_TZ=True)
def test_historical_wall_time_until_uses_zone_rules(case):
    schedule = JSCalendarRecurrence.from_jscalendar(
        {
            "start": case["local"],
            "timeZone": case["zone"],
            "recurrenceRules": [{"frequency": "daily", "until": case["local"]}],
        }
    )
    report = convert_jscalendar_to_icalendar_with_report(schedule, strict=True)
    assert f"UNTIL={case['utc']}" in report.output
    assert schedule.to_jscalendar()["recurrenceRules"][0]["until"] == case["local"]


def test_conversion_reports_ambiguous_and_date_only_values():
    report = convert_icalendar_to_jscalendar_with_report(
        "DTSTART;TZID=America/New_York:20071103T013000\nRRULE:FREQ=DAILY;UNTIL=20071104T063000Z"
    )
    assert not report.lossless
    assert "ambiguous_local_time" in {issue.code for issue in report.issues}
    report = convert_icalendar_to_jscalendar_with_report("DTSTART;VALUE=DATE:20000229")
    assert not report.lossless
    assert "date_value_promoted" in {issue.code for issue in report.issues}


@override_settings(RECURRENCE_USE_TZ=True)
def test_floating_times_are_independent_of_active_timezone():
    text = "DTSTART:20000229T090000\nRRULE:FREQ=DAILY;UNTIL=20000301T090000"
    with django_timezone.override("Asia/Kathmandu"):
        report = convert_icalendar_to_jscalendar_with_report(text)
    assert report.output.dtstart == datetime(2000, 2, 29, 9)
    assert report.output.to_icalendar() == text


def test_fractional_seconds_are_preserved_in_jscalendar_and_reported_in_icalendar():
    schedule = JSCalendarRecurrence.from_jscalendar({"start": "2026-01-01T00:00:00.123456"})
    assert schedule.to_jscalendar()["start"] == "2026-01-01T00:00:00.123456"
    report = convert_jscalendar_to_icalendar_with_report(schedule)
    assert not report.lossless
    assert report.issues[0].code == "fractional_seconds_dropped"
    with pytest.raises(exceptions.ConversionError, match="fractional seconds"):
        convert_jscalendar_to_icalendar_with_report(schedule, strict=True)


def test_leap_second_rule_round_trips_but_cannot_expand():
    text = "DTSTART:20161231T235959Z\nRRULE:FREQ=MINUTELY;BYSECOND=59,60"
    schedule = deserialize_any(text)
    assert schedule.to_icalendar() == text
    assert schedule.to_jscalendar()["recurrenceRules"][0]["bySecond"] == [59, 60]
    with pytest.raises(exceptions.UnsupportedFeatureError, match="Leap-second"):
        list(schedule.occurrences())
    with pytest.raises(exceptions.DeserializationError, match="malformed date-time"):
        deserialize_any("DTSTART:20161231T235960Z")


def test_feature_matrix_completeness():
    assert len(FEATURE_MATRIX) >= 18
    feature_ids = {entry.feature_id for entry in FEATURE_MATRIX}
    expected_ids = {
        "start_dtstart",
        "end_dtend",
        "recurrence_rules",
        "excluded_recurrence_rules",
        "frequency",
        "interval",
        "first_day_of_week",
        "count_until",
        "by_day_nday",
        "by_month",
        "by_month_day",
        "by_year_day",
        "by_week_no",
        "by_hour_minute_second",
        "by_set_position",
        "rscale_skip",
        "rdates_overrides",
        "exdates_overrides",
        "property_patch_overrides",
    }
    assert expected_ids.issubset(feature_ids)
    for entry in FEATURE_MATRIX:
        assert entry.auto_mapping in ("lossless", "conditional", "lossy")
        assert entry.rfc8984_implemented is True


def test_lossless_bidirectional_conversion():
    ical_input = (
        "DTSTART:20260101T090000Z\n"
        "DTEND:20260601T090000Z\n"
        "RRULE:FREQ=MONTHLY;INTERVAL=2;WKST=SU;COUNT=6;BYDAY=1MO,-1FR;BYMONTH=1,3,5\n"
        "RDATE:20260214T090000Z\n"
        "EXDATE:20260302T090000Z"
    )

    report_to_js = convert_icalendar_to_jscalendar_with_report(ical_input)
    assert report_to_js.lossless is True
    assert report_to_js.issues == []

    js_rec: JSCalendarRecurrence = report_to_js.output
    assert len(js_rec.recurrence_rules) == 1
    rule = js_rec.recurrence_rules[0]
    assert rule.frequency == "monthly"
    assert rule.interval == 2
    assert rule.first_day_of_week == "su"
    assert rule.count == 6
    assert rule.by_day == (NDay("mo", 1), NDay("fr", -1))
    assert rule.by_month == ("1", "3", "5")

    report_to_ical = convert_jscalendar_to_icalendar_with_report(js_rec)
    assert report_to_ical.lossless is True
    assert report_to_ical.output == ical_input


def test_conditional_and_lossy_conversion_reports():
    rec = JSCalendarRecurrence(
        start=datetime(2026, 1, 1, 9, 0, 0),
        recurrence_rules=[
            RecurrenceRule(
                frequency=Frequency.YEARLY,
                rscale="hebrew",
                skip=Skip.BACKWARD,
                by_month=["5L"],
                by_month_day=[29],
            ),
            RecurrenceRule(frequency=Frequency.DAILY, count=3),
        ],
        excluded_recurrence_rules=[
            RecurrenceRule(frequency=Frequency.WEEKLY, by_day=["su"]),
        ],
        recurrence_overrides={
            datetime(2026, 1, 2, 9, 0, 0): RecurrenceOverride(
                excluded=False, patches={"title": "Custom Occurrence Title"}
            )
        },
    )

    # Non-strict mode reports issues and marks lossless=False
    report = convert_jscalendar_to_icalendar_with_report(rec, include_rscale=False, strict=False)
    assert report.lossless is False
    issue_codes = {issue.code for issue in report.issues}
    assert "multiple_rrules" in issue_codes
    assert "exrule_mapped" not in issue_codes
    assert "exrule_used" in issue_codes
    assert "non_gregorian_rscale_dropped" in issue_codes
    assert "skip_dropped" in issue_codes
    assert "leap_month_suffix_stripped" in issue_codes
    assert "override_patches_dropped" in issue_codes

    # Strict mode raises ConversionError when lossless is False
    with pytest.raises(exceptions.ConversionError):
        convert_jscalendar_to_icalendar_with_report(rec, include_rscale=False, strict=True)

    # With include_rscale=True, RSCALE and SKIP are emitted in the RRULE
    report_rscale = convert_jscalendar_to_icalendar_with_report(rec, include_rscale=True)
    assert "RSCALE=HEBREW" in report_rscale.output
    assert "SKIP=BACKWARD" in report_rscale.output
    assert "BYMONTH=5L" in report_rscale.output

    # Round-trip the RSCALE/SKIP/5L string back into JSCalendarRecurrence
    parsed_back = convert_icalendar_to_jscalendar_with_report(report_rscale.output).output
    assert parsed_back.recurrence_rules[0].rscale == "hebrew"
    assert parsed_back.recurrence_rules[0].skip == "backward"
    assert parsed_back.recurrence_rules[0].by_month == ("5L",)


def test_deserialize_any_autodetection():
    ical_str = "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"
    js_from_ical = deserialize_any(ical_str)
    assert js_from_ical.recurrence_rules[0].by_day == (NDay("mo"), NDay("we"), NDay("fr"))

    json_str = js_from_ical.to_json()
    js_from_json = deserialize_any(json_str)
    assert js_from_json == js_from_ical

    dict_payload = js_from_ical.to_jscalendar()
    js_from_dict = deserialize_any(dict_payload)
    assert js_from_dict == js_from_ical

    assert deserialize_any(js_from_ical) is js_from_ical

    # Single RecurrenceRule JSON object at root is also accepted
    single_rule_json = js_from_ical.recurrence_rules[0].to_jscalendar()
    js_from_single_rule = deserialize_any(single_rule_json)
    assert js_from_single_rule == js_from_ical


def test_dateutil_rrule_and_rruleset_conversion():
    dtstart = datetime(2026, 1, 5, 9, 0, 0)
    du_rule = dateutil.rrule.rrule(
        freq=dateutil.rrule.MONTHLY,
        interval=2,
        dtstart=dtstart,
        count=4,
        byweekday=(dateutil.rrule.MO(1), dateutil.rrule.FR),
        bymonth=(1, 3, 5),
        bysetpos=(1,),
    )
    converted_rule = recurrence.from_dateutil_rrule(du_rule)
    assert converted_rule.freq == recurrence.MONTHLY
    assert converted_rule.interval == 2
    assert converted_rule.count == 4
    assert recurrence.Weekday(0, 1) in converted_rule.byday
    assert recurrence.Weekday(4) in converted_rule.byday

    du_set = dateutil.rrule.rruleset()
    du_set.rrule(du_rule)
    du_set.rdate(datetime(2026, 2, 1, 9, 0, 0))
    du_set.exdate(datetime(2026, 3, 2, 9, 0, 0))

    converted_rec = recurrence.from_dateutil_rruleset(du_set)
    assert len(converted_rec.rrules) == 1
    assert converted_rec.rdates == [datetime(2026, 2, 1, 9, 0, 0)]
    assert converted_rec.exdates == [datetime(2026, 3, 2, 9, 0, 0)]
