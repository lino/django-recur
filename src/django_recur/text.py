"""Natural language rendering for RFC 8984 RecurrenceRule and legacy Rule objects."""

from __future__ import annotations

import datetime
from typing import Any

from django.utils import dateformat
from django.utils.translation import gettext as _
from django.utils.translation import pgettext as _p

from django_recur.rfc8984 import DayOfWeek, Frequency, NDay, RecurrenceRule


def rule_to_text(rule: RecurrenceRule | Any, short: bool = False) -> str:
    """
    Render an RFC 8984 ``RecurrenceRule`` or legacy ``recurrence.Rule`` as natural text.
    """
    frequencies = (
        _("annually"),
        _("monthly"),
        _("weekly"),
        _("daily"),
        _("hourly"),
        _("minutely"),
        _("secondly"),
    )
    timeintervals = (
        _("years"),
        _("months"),
        _("weeks"),
        _("days"),
        _("hours"),
        _("minutes"),
        _("seconds"),
    )

    if short:
        positional_display = {
            1: _("1st %(weekday)s"),
            2: _("2nd %(weekday)s"),
            3: _("3rd %(weekday)s"),
            4: _("4th %(weekday)s"),
            -1: _("last %(weekday)s"),
            -2: _("2nd last %(weekday)s"),
            -3: _("3rd last %(weekday)s"),
        }
        last_of_month_display = {
            -1: _("last"),
            -2: _("2nd last"),
            -3: _("3rd last"),
            -4: _("4th last"),
        }
        weekdays_display = (
            _("Mon"),
            _("Tue"),
            _("Wed"),
            _("Thu"),
            _("Fri"),
            _("Sat"),
            _("Sun"),
        )
        months_display = (
            _("Jan"),
            _("Feb"),
            _("Mar"),
            _("Apr"),
            _p("month name", "May"),
            _("Jun"),
            _("Jul"),
            _("Aug"),
            _("Sep"),
            _("Oct"),
            _("Nov"),
            _("Dec"),
        )
    else:
        positional_display = {
            1: _("first %(weekday)s"),
            2: _("second %(weekday)s"),
            3: _("third %(weekday)s"),
            4: _("fourth %(weekday)s"),
            -1: _("last %(weekday)s"),
            -2: _("second last %(weekday)s"),
            -3: _("third last %(weekday)s"),
        }
        last_of_month_display = {
            -1: _("last"),
            -2: _("second last"),
            -3: _("third last"),
            -4: _("fourth last"),
        }
        weekdays_display = (
            _("Monday"),
            _("Tuesday"),
            _("Wednesday"),
            _("Thursday"),
            _("Friday"),
            _("Saturday"),
            _("Sunday"),
        )
        months_display = (
            _("January"),
            _("February"),
            _("March"),
            _("April"),
            _p("month name", "May"),
            _("June"),
            _("July"),
            _("August"),
            _("September"),
            _("October"),
            _("November"),
            _("December"),
        )

    # Extract normalized fields whether rule is RecurrenceRule or legacy Rule
    if isinstance(rule, RecurrenceRule):
        freq_index = Frequency(rule.frequency).to_int()
        bymonth = [int(str(m).rstrip("L")) for m in rule.by_month]
        bymonthday = list(rule.by_month_day)
        byday = list(rule.by_day)
        bysetpos = list(rule.by_set_position)
    else:
        freq_index = int(rule.freq)
        bymonth = [int(m) for m in (getattr(rule, "bymonth", None) or [])]
        bymonthday = [int(d) for d in (getattr(rule, "bymonthday", None) or [])]
        raw_byday = getattr(rule, "byday", None) or []
        byday = [
            NDay(day=DayOfWeek.from_int(d.number).value, nth_of_period=d.index)
            if hasattr(d, "number")
            else NDay.from_icalendar(d)
            for d in raw_byday
        ]
        bysetpos = [int(p) for p in (getattr(rule, "bysetpos", None) or [])]

    def get_positional_weekdays() -> str:
        items: list[str] = []
        if bysetpos and byday:
            for setpos in bysetpos:
                for nd in byday:
                    template = positional_display.get(setpos, "%(weekday)s")
                    items.append(template % {"weekday": weekdays_display[nd.number]})
        elif byday:
            for nd in byday:
                template = positional_display.get(nd.nth_of_period, "%(weekday)s")  # type: ignore[arg-type]
                items.append(template % {"weekday": weekdays_display[nd.number]})
        return _(", ").join(items)

    parts: list[str] = []

    if rule.interval > 1:
        parts.append(
            _("every %(number)s %(freq)s")
            % {
                "number": rule.interval,
                "freq": timeintervals[freq_index],
            }
        )
    else:
        parts.append(frequencies[freq_index])

    if freq_index == 0:  # YEARLY
        if bymonth:
            items = _(", ").join([months_display[m - 1] for m in bymonth])
            parts.append(_("each %(items)s") % {"items": items})
        if byday or bysetpos:
            parts.append(_("on the %(items)s") % {"items": get_positional_weekdays()})

    if freq_index == 1:  # MONTHLY
        if bymonthday:
            items = _(", ").join(
                [
                    dateformat.format(datetime.datetime(1, 1, day), "jS")
                    if day > 0
                    else str(last_of_month_display.get(day, day))
                    for day in bymonthday
                ]
            )
            parts.append(_("on the %(items)s") % {"items": items})
        elif byday:
            parts.append(_("on the %(items)s") % {"items": get_positional_weekdays()})

    if freq_index == 2 and byday:  # WEEKLY
        items = _(", ").join([weekdays_display[nd.number] for nd in byday])
        parts.append(_("each %(items)s") % {"items": items})

    if rule.count:
        if rule.count == 1:
            parts.append(_("occuring once"))
        else:
            parts.append(_("occuring %(number)s times") % {"number": rule.count})
    elif rule.until:
        parts.append(_("until %(date)s") % {"date": dateformat.format(rule.until, "Y-m-d")})

    return _(", ").join(parts)
