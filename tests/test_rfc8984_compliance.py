"""
Comprehensive test suite for RFC 8984 (JSCalendar) Section 4.3 compliance.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from dj_recurrence import exceptions
from dj_recurrence.rfc8984 import (
    DayOfWeek,
    Frequency,
    JSCalendarRecurrence,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    Skip,
    format_jscalendar_datetime,
    parse_jscalendar_datetime,
)


def test_frequency_and_dayofweek_enums():
    assert Frequency.from_int(0) == Frequency.YEARLY
    assert Frequency.from_int(6) == Frequency.SECONDLY
    assert Frequency.WEEKLY.to_int() == 2

    with pytest.raises(exceptions.ValidationError):
        Frequency.from_int(99)
    with pytest.raises(exceptions.ValidationError):
        Frequency.from_int(True)

    assert DayOfWeek.from_int(0) == DayOfWeek.MO
    assert DayOfWeek.from_int(6) == DayOfWeek.SU
    assert DayOfWeek.FR.to_int() == 4

    with pytest.raises(ValueError):
        DayOfWeek.from_int(7)
    with pytest.raises(ValueError):
        DayOfWeek.from_int(False)


def test_nday_serialization_and_validation():
    nd = NDay(day="mo", nth_of_period=2)
    assert nd.number == 0
    assert nd.index == 2
    assert nd.to_jscalendar() == {"@type": "NDay", "day": "mo", "nthOfPeriod": 2}
    assert nd.to_icalendar() == "2MO"

    nd_simple = NDay(day=DayOfWeek.FR)
    assert nd_simple.to_jscalendar(include_type=False) == {"day": "fr"}
    assert nd_simple.to_icalendar() == "FR"

    assert NDay.from_jscalendar({"@type": "NDay", "day": "we", "nthOfPeriod": -1}) == NDay(
        day="we", nth_of_period=-1
    )
    assert NDay.from_jscalendar("3TH") == NDay(day="th", nth_of_period=3)
    assert NDay.from_jscalendar(5) == NDay(day="sa")
    assert NDay.from_jscalendar(nd) == nd

    with pytest.raises(exceptions.DeserializationError):
        NDay.from_jscalendar({"@type": "WrongType", "day": "mo"})

    with pytest.raises(exceptions.DeserializationError):
        NDay.from_jscalendar({"@type": "NDay", "day": "mo", "extra": 1})

    with pytest.raises(exceptions.DeserializationError):
        NDay.from_jscalendar({"@type": "NDay", "day": "mo", "nthOfPeriod": 0})

    with pytest.raises(exceptions.DeserializationError):
        NDay.from_jscalendar({"@type": "NDay", "day": "invalid"})

    with pytest.raises(exceptions.DeserializationError):
        NDay.from_jscalendar({"@type": "NDay", "day": 123})

    with pytest.raises(exceptions.DeserializationError):
        NDay.from_jscalendar({"@type": "NDay", "day": "mo", "nthOfPeriod": True})


def test_recurrence_rule_rfc8984_roundtrip():
    rule = RecurrenceRule(
        frequency=Frequency.MONTHLY,
        interval=2,
        rscale="gregorian",
        skip=Skip.OMIT,
        first_day_of_week=DayOfWeek.SU,
        by_day=[NDay("mo", 1), NDay("fr", -1)],
        by_month_day=[1, 15, -1],
        by_month=["1", "6", "12"],
        by_year_day=[1, 100, -1],
        by_week_no=[1, 52],
        by_hour=[9, 17],
        by_minute=[0, 30],
        by_second=[0],
        by_set_position=[1, -1],
        count=10,
    )

    js_dict = rule.to_jscalendar(include_defaults=False)
    assert js_dict == {
        "@type": "RecurrenceRule",
        "frequency": "monthly",
        "interval": 2,
        "firstDayOfWeek": "su",
        "byDay": [
            {"@type": "NDay", "day": "mo", "nthOfPeriod": 1},
            {"@type": "NDay", "day": "fr", "nthOfPeriod": -1},
        ],
        "byMonthDay": [1, 15, -1],
        "byMonth": ["1", "6", "12"],
        "byYearDay": [1, 100, -1],
        "byWeekNo": [1, 52],
        "byHour": [9, 17],
        "byMinute": [0, 30],
        "bySecond": [0],
        "bySetPosition": [1, -1],
        "count": 10,
    }

    parsed = RecurrenceRule.from_jscalendar(js_dict)
    assert parsed == rule

    js_with_defaults = rule.to_jscalendar(include_defaults=True)
    assert js_with_defaults["rscale"] == "gregorian"
    assert js_with_defaults["skip"] == "omit"


def test_recurrence_rule_validation_constraints():
    # count and until are mutually exclusive in strict RFC 8984
    rule_both = RecurrenceRule(
        frequency="daily",
        count=5,
        until=datetime(2026, 1, 10),
    )
    with pytest.raises(exceptions.ValidationError):
        rule_both.validate(strict_rfc8984=True)

    # Zero is disallowed in byMonthDay, byYearDay, byWeekNo, bySetPosition
    with pytest.raises(exceptions.ValidationError):
        RecurrenceRule(frequency="monthly", by_month_day=[0]).validate(strict_rfc8984=True)

    with pytest.raises(exceptions.ValidationError):
        RecurrenceRule(frequency="yearly", by_year_day=[0]).validate(strict_rfc8984=True)

    with pytest.raises(exceptions.ValidationError):
        RecurrenceRule(frequency="yearly", by_week_no=[0]).validate(strict_rfc8984=True)

    with pytest.raises(exceptions.ValidationError):
        RecurrenceRule(frequency="monthly", by_set_position=[0]).validate(strict_rfc8984=True)

    # Invalid skip
    with pytest.raises(exceptions.ValidationError):
        RecurrenceRule(frequency="daily", skip="invalid_skip").validate()

    # Invalid rscale
    with pytest.raises(exceptions.ValidationError):
        RecurrenceRule(frequency="daily", rscale="").validate()

    # Leap month '5L' is allowed when rscale != 'gregorian'
    hebrew_rule = RecurrenceRule(
        frequency="yearly",
        rscale="hebrew",
        by_month=["5L"],
        skip="backward",
    )
    hebrew_rule.validate(strict_rfc8984=True)
    with pytest.raises(exceptions.UnsupportedFeatureError):
        hebrew_rule.to_dateutil_rrule(dtstart=datetime(2026, 1, 1))


def test_rfc8984_skip_backward_and_forward_leap_year():
    # Feb 29 recurrence starting on leap year 2024
    dtstart = datetime(2024, 2, 29, 10, 0, 0)

    rule_omit = RecurrenceRule(
        frequency="yearly",
        by_month=["2"],
        by_month_day=[29],
        skip=Skip.OMIT,
        count=3,
    )
    rec_omit = JSCalendarRecurrence(
        start=dtstart,
        recurrence_rules=[rule_omit],
        include_dtstart=False,
    )
    assert list(rec_omit.occurrences()) == [
        datetime(2024, 2, 29, 10, 0, 0),
        datetime(2028, 2, 29, 10, 0, 0),
        datetime(2032, 2, 29, 10, 0, 0),
    ]

    rule_backward = RecurrenceRule(
        frequency="yearly",
        by_month=["2"],
        by_month_day=[29],
        skip=Skip.BACKWARD,
        count=4,
    )
    rec_backward = JSCalendarRecurrence(
        start=dtstart,
        recurrence_rules=[rule_backward],
        include_dtstart=False,
    )
    assert list(rec_backward.occurrences()) == [
        datetime(2024, 2, 29, 10, 0, 0),
        datetime(2025, 2, 28, 10, 0, 0),
        datetime(2026, 2, 28, 10, 0, 0),
        datetime(2027, 2, 28, 10, 0, 0),
    ]

    rule_forward = RecurrenceRule(
        frequency="yearly",
        by_month=["2"],
        by_month_day=[29],
        skip=Skip.FORWARD,
        count=4,
    )
    rec_forward = JSCalendarRecurrence(
        start=dtstart,
        recurrence_rules=[rule_forward],
        include_dtstart=False,
    )
    assert list(rec_forward.occurrences()) == [
        datetime(2024, 2, 29, 10, 0, 0),
        datetime(2025, 3, 1, 10, 0, 0),
        datetime(2026, 3, 1, 10, 0, 0),
        datetime(2027, 3, 1, 10, 0, 0),
    ]


def test_rfc8984_skip_monthly_31st():
    dtstart = datetime(2026, 1, 31, 9, 0, 0)
    rule_backward = RecurrenceRule(
        frequency="monthly",
        by_month_day=[31],
        skip=Skip.BACKWARD,
        count=4,
    )
    rec = JSCalendarRecurrence(start=dtstart, recurrence_rules=[rule_backward])
    assert list(rec.occurrences()) == [
        datetime(2026, 1, 31, 9, 0, 0),
        datetime(2026, 2, 28, 9, 0, 0),
        datetime(2026, 3, 31, 9, 0, 0),
        datetime(2026, 4, 30, 9, 0, 0),
    ]


def test_jscalendar_recurrence_overrides_and_json_roundtrip():
    rec = JSCalendarRecurrence(
        start=datetime(2026, 5, 1, 12, 0, 0),
        dtend=datetime(2026, 5, 5, 12, 0, 0),
        time_zone="Europe/London",
        recurrence_rules=[RecurrenceRule(frequency="daily")],
        excluded_recurrence_rules=[RecurrenceRule(frequency="weekly", by_day=["su"])],
        recurrence_overrides={
            datetime(2026, 5, 2, 12, 0, 0): RecurrenceOverride(excluded=True),
            datetime(2026, 5, 10, 12, 0, 0): RecurrenceOverride(
                excluded=False, patches={"title": "Special Bonus Session"}
            ),
        },
    )

    json_str = rec.to_json()
    restored = JSCalendarRecurrence.from_json(json_str)

    assert restored == rec
    assert restored.time_zone == "Europe/London"
    assert restored.start == datetime(2026, 5, 1, 12, 0, 0)
    assert restored.exdates == [datetime(2026, 5, 2, 12, 0, 0)]
    assert restored.rdates == [datetime(2026, 5, 10, 12, 0, 0)]
    assert restored.recurrence_overrides[datetime(2026, 5, 10, 12, 0, 0)].patches == {
        "title": "Special Bonus Session"
    }


def test_jscalendar_datetime_parsing_variants():
    dt1 = parse_jscalendar_datetime("2026-03-15T14:30:00Z")
    dt2 = parse_jscalendar_datetime("2026-03-15T14:30:00.123Z")
    dt3 = parse_jscalendar_datetime("2026-03-15")
    dt4 = parse_jscalendar_datetime("20260315")
    assert dt1.year == 2026 and dt1.month == 3 and dt1.day == 15
    assert dt1 == dt2
    assert dt3 == datetime(2026, 3, 15, 0, 0, 0)
    assert dt4 == datetime(2026, 3, 15, 0, 0, 0)
    assert format_jscalendar_datetime(datetime(2026, 3, 15, 14, 30, 0), as_utc=False) == (
        "2026-03-15T14:30:00"
    )

    with pytest.raises(exceptions.DeserializationError):
        parse_jscalendar_datetime("")
    with pytest.raises(exceptions.DeserializationError):
        parse_jscalendar_datetime("not-a-date")


def test_rule_to_text_extended_cases():
    r_monthly_day = RecurrenceRule(frequency="monthly", by_month_day=[1, -1])
    assert r_monthly_day.to_text() == "monthly, on the 1st, last"
    assert r_monthly_day.to_text(short=True) == "monthly, on the 1st, last"

    r_monthly_pos = RecurrenceRule(
        frequency="monthly",
        by_set_position=[-1],
        by_day=[NDay("fr")],
        until=datetime(2026, 12, 31),
    )
    assert r_monthly_pos.to_text() == "monthly, on the last Friday, until 2026-12-31"
