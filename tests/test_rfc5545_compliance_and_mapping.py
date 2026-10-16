"""
Tests for RFC 5545 compliance, the RFC 8984 <-> RFC 5545 Feature Matrix,
bidirectional conversion reports, and dateutil conversion helpers.
"""

from __future__ import annotations

from datetime import datetime

import dateutil.rrule
import pytest

import recurrence
from dj_recurrence import exceptions
from dj_recurrence.rfc5545 import (
    FEATURE_MATRIX,
    convert_icalendar_to_jscalendar_with_report,
    convert_jscalendar_to_icalendar_with_report,
    deserialize_any,
)
from dj_recurrence.rfc8984 import (
    Frequency,
    JSCalendarRecurrence,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    Skip,
)


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
