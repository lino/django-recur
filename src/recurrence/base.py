"""
Drop-in compatibility implementation of ``recurrence.base`` backed internally by
RFC 8984 (JSCalendar) via ``dj_recurrence``.
"""

from __future__ import annotations

import calendar
import datetime
import json
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

import dateutil.rrule

from dj_recurrence.rfc5545 import (
    convert_icalendar_to_jscalendar_with_report,
    serialize_icalendar_dt,
)
from dj_recurrence.rfc8984 import (
    DayOfWeek,
    Frequency,
    JSCalendarRecurrence,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    normalize_offset_awareness,
)
from dj_recurrence.rfc8984 import (
    to_utc as to_utc,
)
from dj_recurrence.text import rule_to_text as _dj_rule_to_text
from recurrence import exceptions

YEARLY, MONTHLY, WEEKLY, DAILY, HOURLY, MINUTELY, SECONDLY = range(7)

(
    JANUARY,
    FEBRUARY,
    MARCH,
    APRIL,
    MAY,
    JUNE,
    JULY,
    AUGUST,
    SEPTEMBER,
    OCTOBER,
    NOVEMBER,
    DECEMBER,
) = range(1, 13)


class Weekday:
    """
    Representation of a weekday (0..6) with an optional positional ``index``
    within the period, backed by RFC 8984 ``NDay``.
    """

    def __init__(self, number: int, index: int | None = None) -> None:
        int(number)
        if number > 6 or number < 0:
            raise ValueError("number must be in range(7)")
        self.number: int = int(number)
        self.index: int | None = index

    def __call__(self, index: int | None) -> Weekday:
        if index == self.index:
            return self
        return Weekday(self.number, index)

    def __hash__(self) -> int:
        if self.index:
            return hash((self.number, self.index))
        return hash(self.number)

    def __eq__(self, other: object) -> bool:
        try:
            other_wd = to_weekday(other)
        except ValueError:
            return False
        return (self.number, self.index) == (other_wd.number, other_wd.index)

    def __repr__(self) -> str:
        if self.index:
            return f"{self.index}{Rule.weekdays[self.number]}"
        return Rule.weekdays[self.number]

    weekday = property(lambda self: self.number)
    n = property(lambda self: self.index)

    def to_nday(self) -> NDay:
        """Convert this ``Weekday`` to an RFC 8984 ``NDay``."""
        return NDay(day=DayOfWeek.from_int(self.number).value, nth_of_period=self.index)

    def to_jscalendar(self) -> dict[str, Any]:
        """Serialize this ``Weekday`` as an RFC 8984 ``NDay`` dictionary."""
        return self.to_nday().to_jscalendar()

    @classmethod
    def from_nday(cls, nday: NDay) -> Weekday:
        """Create a ``Weekday`` from an RFC 8984 ``NDay``."""
        return cls(nday.number, nday.nth_of_period)


MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = (
    MO,
    TU,
    WE,
    TH,
    FR,
    SA,
    SU,
) = WEEKDAYS = [Weekday(n) for n in range(7)]


class Rule:
    """
    A recurrence rule compatible with ``django-recurrence`` and backed internally
    by RFC 8984 ``RecurrenceRule``.
    """

    bysetpos: list[int]
    bymonth: list[int]
    bymonthday: list[int]
    byyearday: list[int]
    byweekno: list[int]
    byday: list[Weekday]
    byhour: list[int]
    byminute: list[int]
    bysecond: list[int]

    byparams = (
        "bysetpos",
        "bymonth",
        "bymonthday",
        "byyearday",
        "byweekno",
        "byday",
        "byhour",
        "byminute",
        "bysecond",
    )
    frequencies = (
        "YEARLY",
        "MONTHLY",
        "WEEKLY",
        "DAILY",
        "HOURLY",
        "MINUTELY",
        "SECONDLY",
    )
    weekdays = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
    firstweekday = calendar.firstweekday()

    def __init__(
        self,
        freq: int | Any,
        interval: int = 1,
        wkst: int | Weekday | None = None,
        count: int | None = None,
        until: datetime.datetime | None = None,
        rscale: str = "gregorian",
        skip: str = "omit",
        **kwargs: Any,
    ) -> None:
        self.freq = freq
        self.interval = interval
        self.wkst = wkst
        self.count = count
        self.until = until
        self.rscale = rscale
        self.skip = skip

        for param in self.byparams:
            if param in kwargs:
                value = kwargs[param]
                if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
                    value = list(value)
                    if not value:
                        value = []
                elif value is not None:
                    value = [value]
                else:
                    value = []
                setattr(self, param, value)
            else:
                setattr(self, param, [])

    def __hash__(self) -> int:
        byparam_values: list[Any] = []
        for param in self.byparams:
            byparam_values.append(param)
            byparam_values.extend(getattr(self, param, []) or [])
        return hash(
            (
                self.freq,
                self.interval,
                self.wkst,
                self.count,
                self.until,
                tuple(byparam_values),
            )
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Rule):
            raise TypeError("object to compare must be Rule object")
        return hash(self) == hash(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def to_text(self, short: bool = False) -> str:
        return rule_to_text(self, short)

    def to_jscalendar_rule(self) -> RecurrenceRule:
        """Convert this ``Rule`` to an RFC 8984 ``RecurrenceRule`` dataclass."""
        validate(self)
        freq_enum = Frequency.from_int(int(self.freq))
        if self.wkst is not None:
            wkst_wd = to_weekday(self.wkst)
            first_day = DayOfWeek.from_int(wkst_wd.number).value
        else:
            first_day = "mo"

        by_day = tuple(to_weekday(d).to_nday() for d in (self.byday or []))
        by_month = tuple(str(int(m)) for m in (self.bymonth or []))

        return RecurrenceRule(
            frequency=freq_enum.value,
            interval=int(self.interval),
            rscale=self.rscale,
            skip=self.skip,
            first_day_of_week=first_day,
            by_day=by_day,
            by_month_day=tuple(int(x) for x in (self.bymonthday or [])),
            by_month=by_month,
            by_year_day=tuple(int(x) for x in (self.byyearday or [])),
            by_week_no=tuple(int(x) for x in (self.byweekno or [])),
            by_hour=tuple(int(x) for x in (self.byhour or [])),
            by_minute=tuple(int(x) for x in (self.byminute or [])),
            by_second=tuple(int(x) for x in (self.bysecond or [])),
            by_set_position=tuple(int(x) for x in (self.bysetpos or [])),
            count=int(self.count) if self.count is not None else None,
            until=self.until if self.count is None else None,
        )

    def to_jscalendar(self, include_defaults: bool = False) -> dict[str, Any]:
        """Serialize this ``Rule`` to an RFC 8984 ``RecurrenceRule`` dictionary."""
        js_rule = self.to_jscalendar_rule()
        data = js_rule.to_jscalendar(include_defaults=include_defaults)
        if self.wkst is not None and not include_defaults:
            wkst_wd = to_weekday(self.wkst)
            if wkst_wd.number != 0:
                data["firstDayOfWeek"] = DayOfWeek.from_int(wkst_wd.number).value
        return data

    @classmethod
    def from_jscalendar(cls, data: Mapping[str, Any] | RecurrenceRule) -> Rule:
        """Create a ``Rule`` from an RFC 8984 ``RecurrenceRule`` or dictionary."""
        js_rule = data if isinstance(data, RecurrenceRule) else RecurrenceRule.from_jscalendar(data)
        freq_int = Frequency(js_rule.frequency).to_int()
        wkst: int | None = None
        if js_rule.first_day_of_week and js_rule.first_day_of_week != "mo":
            wkst = DayOfWeek(str(js_rule.first_day_of_week)).to_int()
        elif isinstance(data, Mapping) and "firstDayOfWeek" in data:
            wkst = DayOfWeek(str(data["firstDayOfWeek"]).lower()).to_int()

        byday = [Weekday.from_nday(nd) for nd in js_rule.by_day]
        bymonth = [int(str(m).rstrip("L")) for m in js_rule.by_month]

        return cls(
            freq=freq_int,
            interval=int(js_rule.interval),
            wkst=wkst,
            count=js_rule.count,
            until=js_rule.until,
            rscale=js_rule.rscale,
            skip=js_rule.skip,
            byday=byday,
            bymonth=bymonth,
            bymonthday=list(js_rule.by_month_day),
            byyearday=list(js_rule.by_year_day),
            byweekno=list(js_rule.by_week_no),
            byhour=list(js_rule.by_hour),
            byminute=list(js_rule.by_minute),
            bysecond=list(js_rule.by_second),
            bysetpos=list(js_rule.by_set_position),
        )

    from_jscalendar_rule = from_jscalendar

    def to_dateutil_rrule(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> dateutil.rrule.rrule:
        return self.to_jscalendar_rule().to_dateutil_rrule(
            dtstart=dtstart, dtend=dtend, cache=cache
        )


class Recurrence:
    """
    A combination of ``Rule`` and ``datetime.datetime`` instances compatible with
    ``django-recurrence`` and backed internally by RFC 8984 ``JSCalendarRecurrence``.
    """

    def __init__(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        rrules: Iterable[Rule] = (),
        exrules: Iterable[Rule] = (),
        rdates: Iterable[datetime.datetime] = (),
        exdates: Iterable[datetime.datetime] = (),
        include_dtstart: bool = True,
    ) -> None:
        self._cache: dict[Any, dateutil.rrule.rruleset] = {}
        self.dtstart = dtstart
        self.dtend = dtend
        self.rrules: list[Rule] = list(rrules)
        self.exrules: list[Rule] = list(exrules)
        self.rdates: list[datetime.datetime] = list(rdates)
        self.exdates: list[datetime.datetime] = list(exdates)
        self.include_dtstart = include_dtstart

    def to_jscalendar_recurrence(self) -> JSCalendarRecurrence:
        """Convert this ``Recurrence`` to an RFC 8984 ``JSCalendarRecurrence``."""
        validate(self)
        overrides: dict[datetime.datetime, RecurrenceOverride] = {}
        for rdate in self.rdates:
            overrides[rdate] = RecurrenceOverride(excluded=False)
        for exdate in self.exdates:
            overrides[exdate] = RecurrenceOverride(excluded=True)

        return JSCalendarRecurrence(
            dtstart=self.dtstart,
            dtend=self.dtend,
            recurrence_rules=[r.to_jscalendar_rule() for r in self.rrules],
            excluded_recurrence_rules=[r.to_jscalendar_rule() for r in self.exrules],
            recurrence_overrides=overrides,
            include_dtstart=self.include_dtstart,
        )

    to_jscalendar_obj = to_jscalendar_recurrence

    def to_jscalendar(self, include_defaults: bool = False) -> dict[str, Any]:
        """Serialize this ``Recurrence`` to an RFC 8984 JSCalendar dictionary."""
        return self.to_jscalendar_recurrence().to_jscalendar(include_defaults=include_defaults)

    to_jscalendar_dict = to_jscalendar

    def to_json(self, indent: int | None = None) -> str:
        """Serialize this ``Recurrence`` to an RFC 8984 JSCalendar JSON string."""
        return json.dumps(self.to_jscalendar(), indent=indent)

    to_jscalendar_json = to_json

    @classmethod
    def from_jscalendar(
        cls,
        data: Mapping[str, Any] | str | JSCalendarRecurrence,
        include_dtstart: bool = True,
    ) -> Recurrence:
        """Create a ``Recurrence`` from an RFC 8984 dictionary, JSON string, or object."""
        js_rec = (
            data
            if isinstance(data, JSCalendarRecurrence)
            else JSCalendarRecurrence.from_jscalendar(data, include_dtstart=include_dtstart)
        )
        return cls(
            dtstart=js_rec.dtstart,
            dtend=js_rec.dtend,
            rrules=[Rule.from_jscalendar(r) for r in js_rec.recurrence_rules],
            exrules=[Rule.from_jscalendar(r) for r in js_rec.excluded_recurrence_rules],
            rdates=js_rec.rdates,
            exdates=js_rec.exdates,
            include_dtstart=js_rec.include_dtstart,
        )

    from_jscalendar_obj = from_jscalendar

    def __iter__(self) -> Iterator[datetime.datetime]:
        return iter(self.occurrences())

    def __str__(self) -> str:
        return serialize(self) or ""

    def __hash__(self) -> int:
        return hash(
            (
                self.dtstart,
                self.dtend,
                tuple(self.rrules),
                tuple(self.exrules),
                tuple(self.rdates),
                tuple(self.exdates),
            )
        )

    def __bool__(self) -> bool:
        return bool(
            self.dtstart
            or self.dtend
            or tuple(self.rrules)
            or tuple(self.exrules)
            or tuple(self.rdates)
            or tuple(self.exdates)
        )

    def __nonzero__(self) -> bool:
        return type(self).__bool__(self)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        return hash(self) == hash(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def occurrences(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> dateutil.rrule.rruleset:
        return self.to_dateutil_rruleset(dtstart, dtend, cache)

    def count(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> int:
        return int(self.to_dateutil_rruleset(dtstart, dtend, cache).count() or 0)

    def before(
        self,
        dt: datetime.datetime,
        inc: bool = False,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> datetime.datetime | None:
        return self.to_dateutil_rruleset(dtstart, dtend, cache).before(dt, inc)

    def after(
        self,
        dt: datetime.datetime,
        inc: bool = False,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> datetime.datetime | None:
        return self.to_dateutil_rruleset(dtstart, dtend, cache).after(dt, inc)

    def between(
        self,
        after: datetime.datetime,
        before: datetime.datetime,
        inc: bool = False,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> list[datetime.datetime]:
        return list(self.to_dateutil_rruleset(dtstart, dtend, cache).between(after, before, inc))

    def to_dateutil_rruleset(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> dateutil.rrule.rruleset:
        eff_dtstart = dtstart or self.dtstart
        eff_dtend = dtend or self.dtend

        if eff_dtend:
            eff_dtend = normalize_offset_awareness(eff_dtend, eff_dtstart)

        if cache:
            cached = self._cache.get(eff_dtstart)
            if cached:
                return cached

        rruleset = self.to_jscalendar_recurrence().to_dateutil_rruleset(
            dtstart=eff_dtstart, dtend=eff_dtend, cache=cache
        )

        if cache:
            self._cache[eff_dtstart] = rruleset

        return rruleset


def to_weekday(token: Any) -> Weekday:
    """
    Convert a token (``Weekday``, ``NDay``, ``dateutil.rrule.weekday``, ``int``, or ``str``)
    to a ``Weekday`` instance.
    """
    if isinstance(token, Weekday):
        return token
    if isinstance(token, NDay):
        return Weekday.from_nday(token)
    if isinstance(token, dateutil.rrule.weekday):
        return Weekday(token.weekday, token.n)
    if isinstance(token, int) and not isinstance(token, bool):
        if token > 6 or token < 0:
            raise ValueError(f"Weekday out of range: {token}")
        return WEEKDAYS[token]
    if not token:
        raise ValueError(f"Empty weekday token: {token!r}")
    if isinstance(token, str) and token.isdigit():
        if int(token) > 6:
            raise ValueError(f"Weekday out of range: {token}")
        return WEEKDAYS[int(token)]
    if isinstance(token, str):
        const = token[-2:].upper()
        if const not in Rule.weekdays:
            raise ValueError(f"Invalid weekday constant: {token!r}")
        nth = token[:-2]
        if not nth:
            return Weekday(list(Rule.weekdays).index(const))
        return Weekday(list(Rule.weekdays).index(const), int(nth))
    raise ValueError(f"Invalid weekday token: {token!r}")


def validate(rule_or_recurrence: Any) -> None:
    """Validate a ``Rule``, ``Recurrence``, ``RecurrenceRule``, or ``JSCalendarRecurrence``."""
    if isinstance(rule_or_recurrence, (RecurrenceRule, JSCalendarRecurrence)):
        rule_or_recurrence.validate(strict_rfc8984=False)
        return

    if isinstance(rule_or_recurrence, Rule):
        obj = Recurrence(rrules=[rule_or_recurrence])
    else:
        obj = rule_or_recurrence

    if not isinstance(obj, Recurrence):
        raise exceptions.ValidationError("incompatible object")

    def validate_dt(dt: Any) -> None:
        if not isinstance(dt, datetime.datetime):
            raise exceptions.ValidationError(f"invalid datetime: {dt!r}")

    def validate_iterable_ints(
        rule: Rule,
        param: str,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> None:
        raw_seq = getattr(rule, param, [])
        try:
            iter(raw_seq)
        except TypeError as exc:
            raise exceptions.ValidationError(f"{param} parameter must be iterable") from exc

        for value in raw_seq:
            try:
                if isinstance(value, bool):
                    raise ValueError
                iv = int(value)
                if min_value is not None and iv < min_value:
                    raise ValueError
                if max_value is not None and iv > max_value:
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise exceptions.ValidationError(f"invalid {param} parameter: {value!r}") from exc

    def validate_rule(rule: Any) -> None:
        if not isinstance(rule, Rule):
            raise exceptions.ValidationError("incompatible object")
        try:
            if isinstance(rule.freq, bool) or int(rule.freq) < 0:
                raise ValueError
            Rule.frequencies[int(rule.freq)]
        except (IndexError, ValueError, TypeError) as exc:
            raise exceptions.ValidationError(f"invalid freq parameter: {rule.freq!r}") from exc

        try:
            if isinstance(rule.interval, bool):
                raise ValueError
            interval = int(rule.interval)
            if interval < 1:
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise exceptions.ValidationError(
                f"invalid interval parameter: {rule.interval!r}"
            ) from exc

        if rule.wkst:
            try:
                to_weekday(rule.wkst)
            except ValueError as exc:
                raise exceptions.ValidationError(f"invalide wkst parameter: {rule.wkst!r}") from exc

        if rule.until is not None:
            validate_dt(rule.until)

        if rule.count is not None:
            try:
                if isinstance(rule.count, bool):
                    raise ValueError
                int(rule.count)
            except (ValueError, TypeError) as exc:
                raise exceptions.ValidationError(
                    f"invalid count parameter: {rule.count!r}"
                ) from exc

        for param in Rule.byparams:
            if param == "byday":
                raw_byday = getattr(rule, "byday", [])
                try:
                    iter(raw_byday)
                except TypeError as exc:
                    raise exceptions.ValidationError("byday parameter must be iterable") from exc
                for value in raw_byday:
                    try:
                        to_weekday(value)
                    except ValueError as exc:
                        raise exceptions.ValidationError(
                            f"invalid byday parameter: {value!r}"
                        ) from exc
            elif param == "bymonth":
                validate_iterable_ints(rule, param, 1, 12)
            elif param == "bymonthday":
                validate_iterable_ints(rule, param, -31, 31)
            elif param == "byhour":
                validate_iterable_ints(rule, param, 0, 23)
            elif param in ("byminute", "bysecond"):
                validate_iterable_ints(rule, param, 0, 59)
            else:
                validate_iterable_ints(rule, param)

    if obj.dtstart:
        validate_dt(obj.dtstart)
    if obj.dtend:
        validate_dt(obj.dtend)
    if obj.rrules:
        for r in obj.rrules:
            validate_rule(r)
    if obj.exrules:
        for r in obj.exrules:
            validate_rule(r)
    if obj.rdates:
        for dt in obj.rdates:
            validate_dt(dt)
    if obj.exdates:
        for dt in obj.exdates:
            validate_dt(dt)


def serialize(
    rule_or_recurrence: Rule | Recurrence | RecurrenceRule | JSCalendarRecurrence | None,
    output_format: str = "rfc5545",
) -> str | None:
    """
    Serialize a ``Rule`` or ``Recurrence`` instance to RFC 5545 (default) or RFC 8984 JSON.
    """
    if rule_or_recurrence is None:
        return None

    try:
        validate(rule_or_recurrence)
    except exceptions.ValidationError as error:
        raise exceptions.SerializationError(error.args[0]) from error

    if isinstance(rule_or_recurrence, (RecurrenceRule, JSCalendarRecurrence)):
        if output_format.lower() in ("rfc8984", "jscalendar", "json"):
            if isinstance(rule_or_recurrence, RecurrenceRule):
                return json.dumps(rule_or_recurrence.to_jscalendar())
            return rule_or_recurrence.to_json()
        if isinstance(rule_or_recurrence, RecurrenceRule):
            return JSCalendarRecurrence(recurrence_rules=[rule_or_recurrence]).to_icalendar()
        return rule_or_recurrence.to_icalendar()

    obj = (
        Recurrence(rrules=[rule_or_recurrence])
        if isinstance(rule_or_recurrence, Rule)
        else rule_or_recurrence
    )

    if output_format.lower() in ("rfc8984", "jscalendar", "json"):
        return obj.to_json()

    def serialize_rule(rule: Rule) -> str:
        values: list[tuple[str, list[str]]] = []
        values.append(("FREQ", [Rule.frequencies[int(rule.freq)]]))

        if rule.interval != 1:
            values.append(("INTERVAL", [str(int(rule.interval))]))
        if rule.wkst:
            wkst_num: Any = getattr(rule.wkst, "number", rule.wkst)
            values.append(("WKST", [Rule.weekdays[int(wkst_num)]]))

        if rule.count is not None:
            values.append(("COUNT", [str(rule.count)]))
        elif rule.until is not None:
            values.append(("UNTIL", [serialize_icalendar_dt(rule.until)]))

        if rule.byday:
            days = [repr(to_weekday(d)) for d in rule.byday]
            values.append(("BYDAY", days))

        for param in Rule.byparams:
            if param == "byday":
                continue
            value_list = getattr(rule, param, None)
            if value_list:
                values.append((param.upper(), [str(n) for n in value_list]))

        return ";".join(f"{k}={','.join(v)}" for k, v in values)

    items: list[tuple[str, str]] = []
    if obj.dtstart:
        items.append(("DTSTART", serialize_icalendar_dt(obj.dtstart)))
    if obj.dtend:
        items.append(("DTEND", serialize_icalendar_dt(obj.dtend)))

    for rrule in obj.rrules:
        items.append(("RRULE", serialize_rule(rrule)))
    for exrule in obj.exrules:
        items.append(("EXRULE", serialize_rule(exrule)))

    for rdate in obj.rdates:
        items.append(("RDATE", serialize_icalendar_dt(rdate)))
    for exdate in obj.exdates:
        items.append(("EXDATE", serialize_icalendar_dt(exdate)))

    return "\n".join(f"{k}:{v}" for k, v in items)


def serialize_jscalendar(rule_or_recurrence: Rule | Recurrence | None) -> dict[str, Any] | None:
    """Serialize a ``Rule`` or ``Recurrence`` to an RFC 8984 JSCalendar dictionary."""
    if rule_or_recurrence is None:
        return None
    try:
        validate(rule_or_recurrence)
    except exceptions.ValidationError as error:
        raise exceptions.SerializationError(error.args[0]) from error
    return rule_or_recurrence.to_jscalendar()


def deserialize(
    text: str | Mapping[str, Any] | Recurrence | JSCalendarRecurrence,
    include_dtstart: bool = True,
) -> Recurrence:
    """
    Deserialize an RFC 2445 / RFC 5545 string OR an RFC 8984 JSCalendar JSON string/dict
    into a ``Recurrence`` instance (backed by RFC 8984).
    """
    if isinstance(text, Recurrence):
        return text
    if isinstance(text, JSCalendarRecurrence):
        return Recurrence.from_jscalendar(text, include_dtstart=include_dtstart)
    if isinstance(text, Mapping):
        return Recurrence.from_jscalendar(text, include_dtstart=include_dtstart)
    if not isinstance(text, str):
        raise TypeError("text to deserialize must be a string or mapping")

    stripped = text.strip()
    if stripped.startswith("{"):
        return Recurrence.from_jscalendar(stripped, include_dtstart=include_dtstart)

    report = convert_icalendar_to_jscalendar_with_report(text, include_dtstart=include_dtstart)
    return Recurrence.from_jscalendar(report.output, include_dtstart=include_dtstart)


def rule_to_text(rule: Rule | RecurrenceRule, short: bool = False) -> str:
    """Render the given ``Rule`` as natural text."""
    return _dj_rule_to_text(rule, short=short)


def from_dateutil_rrule(rrule: Any) -> Rule:
    """Convert a ``dateutil.rrule.rrule`` instance to a ``Rule`` instance."""
    kwargs: dict[str, Any] = {}
    kwargs["freq"] = rrule._freq
    kwargs["interval"] = rrule._interval
    if rrule._wkst != 0:
        kwargs["wkst"] = rrule._wkst
    kwargs["bysetpos"] = rrule._bysetpos
    if rrule._count is not None:
        kwargs["count"] = rrule._count
    elif rrule._until is not None:
        kwargs["until"] = rrule._until

    days: list[Weekday] = []
    if rrule._byweekday is not None and (
        rrule._freq != WEEKLY
        or len(rrule._byweekday) != 1
        or rrule._dtstart.weekday() != rrule._byweekday[0]
    ):
        days.extend(Weekday(n) for n in rrule._byweekday)

    if rrule._bynweekday is not None:
        days.extend(Weekday(*n) for n in rrule._bynweekday)

    if len(days) > 0:
        kwargs["byday"] = days

    if (
        rrule._bymonthday is not None
        and len(rrule._bymonthday) > 0
        and not (
            rrule._freq <= MONTHLY
            and len(rrule._bymonthday) == 1
            and rrule._bymonthday[0] == rrule._dtstart.day
        )
    ):
        kwargs["bymonthday"] = list(rrule._bymonthday)

    if rrule._bynmonthday is not None and len(rrule._bynmonthday) > 0:
        kwargs.setdefault("bymonthday", []).extend(rrule._bynmonthday)

    if (
        rrule._bymonth is not None
        and len(rrule._bymonth) > 0
        and (
            rrule._byweekday is not None
            or len(rrule._bynweekday or ()) > 0
            or not (
                rrule._freq == YEARLY
                and len(rrule._bymonth) == 1
                and rrule._bymonth[0] == rrule._dtstart.month
            )
        )
    ):
        kwargs["bymonth"] = list(rrule._bymonth)

    if rrule._byyearday is not None:
        kwargs["byyearday"] = list(rrule._byyearday)
    if rrule._byweekno is not None:
        kwargs["byweekno"] = list(rrule._byweekno)

    kwargs["byhour"] = list(rrule._byhour)
    kwargs["byminute"] = list(rrule._byminute)
    kwargs["bysecond"] = list(rrule._bysecond)
    if (
        rrule._dtstart.hour in rrule._byhour
        and rrule._dtstart.minute in rrule._byminute
        and rrule._dtstart.second in rrule._bysecond
    ):
        kwargs["byhour"].remove(rrule._dtstart.hour)
        kwargs["byminute"].remove(rrule._dtstart.minute)
        kwargs["bysecond"].remove(rrule._dtstart.second)

    return Rule(**kwargs)


def from_dateutil_rruleset(rruleset: Any) -> Recurrence:
    """Convert a ``dateutil.rrule.rruleset`` instance to a ``Recurrence`` instance."""
    rrules = [from_dateutil_rrule(rrule) for rrule in rruleset._rrule]
    exrules = [from_dateutil_rrule(exrule) for exrule in rruleset._exrule]
    rdates = list(rruleset._rdate)
    exdates = list(rruleset._exdate)

    dts = [r._dtstart for r in rruleset._rrule] + rdates
    if len(dts) > 0:
        dts.sort()
        dtstart = dts[0]
    else:
        dtstart = None

    return Recurrence(
        dtstart=dtstart, rrules=rrules, exrules=exrules, rdates=rdates, exdates=exdates
    )
