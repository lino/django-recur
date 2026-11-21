"""
RFC 8984 (JSCalendar) recurrence data structures, validation, serialization,
and occurrence expansion engine.

Implements Section 4.3 of RFC 8984:
- ``NDay``
- ``RecurrenceRule``
- ``RecurrenceOverride``
- ``JSCalendarRecurrence``
"""

from __future__ import annotations

import calendar
import datetime
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import dateutil.rrule
from dateutil import tz
from django.conf import settings as django_settings
from django.utils.timezone import get_current_timezone, is_aware, is_naive, make_aware

from django_recur import exceptions


class Frequency(str, Enum):
    """RFC 8984 RecurrenceRule frequency values (lowercase strings)."""

    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"
    HOURLY = "hourly"
    MINUTELY = "minutely"
    SECONDLY = "secondly"

    @classmethod
    def from_int(cls, value: int) -> Frequency:
        try:
            if isinstance(value, bool) or int(value) < 0:
                raise ValueError(f"Invalid frequency index: {value!r}")
            return _FREQUENCIES_BY_INDEX[int(value)]
        except (IndexError, ValueError, TypeError) as exc:
            raise exceptions.ValidationError(f"invalid freq parameter: {value!r}") from exc

    def to_int(self) -> int:
        return _FREQUENCIES_BY_INDEX.index(self)


_FREQUENCIES_BY_INDEX: tuple[Frequency, ...] = (
    Frequency.YEARLY,
    Frequency.MONTHLY,
    Frequency.WEEKLY,
    Frequency.DAILY,
    Frequency.HOURLY,
    Frequency.MINUTELY,
    Frequency.SECONDLY,
)


class DayOfWeek(str, Enum):
    """RFC 8984 day of week identifiers (lowercase two-letter strings)."""

    MO = "mo"
    TU = "tu"
    WE = "we"
    TH = "th"
    FR = "fr"
    SA = "sa"
    SU = "su"

    @classmethod
    def from_int(cls, value: int) -> DayOfWeek:
        if isinstance(value, bool) or not (0 <= int(value) <= 6):
            raise ValueError(f"Weekday number must be in range(7), got {value!r}")
        return _DAYS_BY_INDEX[int(value)]

    def to_int(self) -> int:
        return _DAYS_BY_INDEX.index(self)


_DAYS_BY_INDEX: tuple[DayOfWeek, ...] = (
    DayOfWeek.MO,
    DayOfWeek.TU,
    DayOfWeek.WE,
    DayOfWeek.TH,
    DayOfWeek.FR,
    DayOfWeek.SA,
    DayOfWeek.SU,
)


class Skip(str, Enum):
    """RFC 8984 / RFC 7529 skip behavior for invalid dates in recurrence expansion."""

    OMIT = "omit"
    BACKWARD = "backward"
    FORWARD = "forward"


def deserialize_tz_enabled() -> bool:
    """Return whether deserialized datetimes should be timezone-aware."""
    try:
        return bool(django_settings.RECURRENCE_USE_TZ)
    except AttributeError:
        return bool(getattr(django_settings, "USE_TZ", False))


def to_utc(dt: datetime.datetime | None) -> datetime.datetime | None:
    """Convert a naive or aware datetime to UTC."""
    if not dt:
        return dt
    if is_naive(dt):
        dt = make_aware(dt)
    return dt.astimezone(tz.UTC)


def normalize_offset_awareness(
    dt: datetime.datetime,
    from_dt: datetime.datetime | None = None,
) -> datetime.datetime:
    """
    Normalize ``dt`` to match the timezone awareness of ``from_dt``.
    """
    if from_dt and is_aware(from_dt) and is_aware(dt):
        return dt
    if from_dt and is_aware(from_dt) and is_naive(dt):
        return make_aware(dt, from_dt.tzinfo)
    if is_aware(dt):
        local_dt = dt.astimezone(get_current_timezone())
        return datetime.datetime(
            local_dt.year,
            local_dt.month,
            local_dt.day,
            local_dt.hour,
            local_dt.minute,
            local_dt.second,
        )
    return dt


def format_jscalendar_datetime(dt: datetime.datetime, as_utc: bool = True) -> str:
    """
    Format a ``datetime`` as an RFC 8984 ``UTCDateTime`` or ``LocalDateTime`` string
    (ISO 8601 extended format ``YYYY-MM-DDTHH:MM:SS[Z]``).
    """
    if as_utc:
        utc_dt = to_utc(dt)
        assert utc_dt is not None
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if is_aware(dt):
        utc_dt = dt.astimezone(tz.UTC)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_jscalendar_datetime(
    text: str, *, local: bool = False, time_zone: datetime.tzinfo | None = None
) -> datetime.datetime:
    """
    Parse an RFC 8984 ``LocalDateTime`` or ``UTCDateTime`` (or compact ISO/RFC 5545 string)
    into a ``datetime.datetime`` respecting ``RECURRENCE_USE_TZ`` / ``USE_TZ``.
    """
    if not isinstance(text, str) or not text.strip():
        raise exceptions.DeserializationError(f"malformed date-time: {text!r}")

    cleaned = text.strip()
    is_utc_marker = cleaned.endswith("Z") or cleaned.endswith("z")
    cleaned_no_z = cleaned[:-1] if is_utc_marker else cleaned

    try:
        microsecond = 0
        if "-" in cleaned_no_z:
            # ISO 8601 extended format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
            if "T" in cleaned_no_z or "t" in cleaned_no_z:
                date_part, time_part = cleaned_no_z.replace("t", "T").split("T", 1)
                if "." in time_part:
                    time_part, fraction = time_part.split(".", 1)
                    if not fraction.isascii() or not fraction.isdecimal():
                        raise ValueError("Invalid fractional seconds")
                    if local:
                        if len(fraction) > 6:
                            raise ValueError("Fractional seconds exceed datetime precision")
                        microsecond = int(fraction.ljust(6, "0"))
                year_s, month_s, day_s = date_part.split("-")
                hour_s, minute_s, second_s = time_part.split(":")
                year, month, day = int(year_s), int(month_s), int(day_s)
                hour, minute, second = int(hour_s), int(minute_s), int(second_s)
            else:
                year_s, month_s, day_s = cleaned_no_z.split("-")
                year, month, day = int(year_s), int(month_s), int(day_s)
                hour, minute, second = 0, 0, 0
        else:
            # Compact RFC 5545 format: YYYYMMDD or YYYYMMDDTHHMMSS
            if len(cleaned_no_z) < 8:
                raise ValueError("Date string too short")
            year, month, day = (
                int(cleaned_no_z[:4]),
                int(cleaned_no_z[4:6]),
                int(cleaned_no_z[6:8]),
            )
            if "T" in cleaned_no_z:
                if len(cleaned_no_z) < 15:
                    raise ValueError("Time string too short")
                hour, minute, second = (
                    int(cleaned_no_z[9:11]),
                    int(cleaned_no_z[11:13]),
                    int(cleaned_no_z[13:15]),
                )
            else:
                hour, minute, second = 0, 0, 0

        tzinfo: datetime.tzinfo | None
        if is_utc_marker:
            tzinfo = tz.UTC
        elif local:
            tzinfo = time_zone
        else:
            tzinfo = get_current_timezone()
        dt = datetime.datetime(year, month, day, hour, minute, second, microsecond, tzinfo)
    except (ValueError, TypeError) as exc:
        raise exceptions.DeserializationError(f"malformed date-time: {text!r}") from exc

    if local:
        if is_utc_marker and time_zone is not None:
            dt = dt.astimezone(time_zone)
        elif is_utc_marker and not deserialize_tz_enabled():
            dt = dt.astimezone(get_current_timezone())
        return dt if deserialize_tz_enabled() else dt.replace(tzinfo=None)

    if deserialize_tz_enabled():
        return dt

    local_dt = dt.astimezone(get_current_timezone())
    return datetime.datetime(
        local_dt.year,
        local_dt.month,
        local_dt.day,
        local_dt.hour,
        local_dt.minute,
        local_dt.second,
    )


def calendar_time_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise exceptions.DeserializationError(f"Unknown time zone: {name!r}") from exc


def format_local_datetime(
    value: datetime.datetime, time_zone: datetime.tzinfo | None = None
) -> str:
    if is_aware(value) and time_zone is not None:
        value = value.astimezone(time_zone)
    return value.replace(tzinfo=None).isoformat()


@dataclass(frozen=True)
class NDay:
    """
    RFC 8984 Section 4.3.3 ``NDay`` object representing a weekday with an optional
    positional occurrence within the period (``nthOfPeriod``).
    """

    day: str
    nth_of_period: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.day, DayOfWeek):
            object.__setattr__(self, "day", self.day.value)
        elif isinstance(self.day, str):
            object.__setattr__(self, "day", self.day.lower().strip())
        elif isinstance(self.day, int) and not isinstance(self.day, bool):
            object.__setattr__(self, "day", DayOfWeek.from_int(self.day).value)

        if self.nth_of_period == 0:
            object.__setattr__(self, "nth_of_period", None)

    @property
    def number(self) -> int:
        """Return 0-indexed weekday integer (0 = Monday .. 6 = Sunday)."""
        return DayOfWeek(self.day).to_int()

    @property
    def index(self) -> int | None:
        """Alias for ``nth_of_period`` for compatibility with ``recurrence.Weekday``."""
        return self.nth_of_period

    def validate(self) -> None:
        try:
            DayOfWeek(self.day)
        except ValueError as exc:
            raise exceptions.ValidationError(f"invalid NDay.day: {self.day!r}") from exc

        if self.nth_of_period is not None:
            if isinstance(self.nth_of_period, bool) or not isinstance(self.nth_of_period, int):
                raise exceptions.ValidationError(
                    f"invalid NDay.nthOfPeriod: {self.nth_of_period!r}"
                )
            if self.nth_of_period == 0 or not (-366 <= self.nth_of_period <= 366):
                raise exceptions.ValidationError(
                    f"invalid NDay.nthOfPeriod out of range: {self.nth_of_period!r}"
                )

    def to_jscalendar(self, include_type: bool = True) -> dict[str, Any]:
        self.validate()
        result: dict[str, Any] = {}
        if include_type:
            result["@type"] = "NDay"
        result["day"] = self.day
        if self.nth_of_period is not None:
            result["nthOfPeriod"] = self.nth_of_period
        return result

    @classmethod
    def from_jscalendar(cls, data: Mapping[str, Any] | NDay | str | int) -> NDay:
        if isinstance(data, NDay):
            data.validate()
            return data
        if isinstance(data, int) and not isinstance(data, bool):
            nday = cls(day=DayOfWeek.from_int(data).value)
            nday.validate()
            return nday
        if isinstance(data, str):
            return cls.from_icalendar(data)
        if not isinstance(data, Mapping):
            raise exceptions.DeserializationError(f"Invalid NDay object: {data!r}")

        obj_type = data.get("@type")
        if obj_type is not None and obj_type != "NDay":
            raise exceptions.DeserializationError(f"Invalid NDay @type: {obj_type!r}")

        allowed_keys = {"@type", "day", "nthOfPeriod"}
        unknown_keys = set(data.keys()) - allowed_keys
        if unknown_keys:
            raise exceptions.DeserializationError(
                f"Unknown NDay properties: {sorted(unknown_keys)}"
            )

        day_raw = data.get("day")
        if not isinstance(day_raw, str):
            raise exceptions.DeserializationError(f"Missing or invalid NDay.day: {day_raw!r}")

        nth_raw = data.get("nthOfPeriod")
        if nth_raw is not None and (isinstance(nth_raw, bool) or not isinstance(nth_raw, int)):
            raise exceptions.DeserializationError(f"Invalid NDay.nthOfPeriod: {nth_raw!r}")
        if nth_raw == 0:
            raise exceptions.DeserializationError("NDay.nthOfPeriod cannot be 0")

        try:
            nday = cls(day=day_raw.lower(), nth_of_period=nth_raw)
            nday.validate()
        except exceptions.ValidationError as exc:
            raise exceptions.DeserializationError(str(exc.args[0])) from exc
        return nday

    def to_icalendar(self) -> str:
        self.validate()
        code = self.day.upper()
        if self.nth_of_period:
            return f"{self.nth_of_period}{code}"
        return code

    @classmethod
    def from_icalendar(cls, token: str | int | dateutil.rrule.weekday) -> NDay:
        if isinstance(token, dateutil.rrule.weekday):
            return cls(day=DayOfWeek.from_int(token.weekday).value, nth_of_period=token.n)
        if isinstance(token, int) and not isinstance(token, bool):
            if not (0 <= token <= 6):
                raise ValueError(f"Weekday integer out of range: {token}")
            return cls(day=DayOfWeek.from_int(token).value)
        if not token or not isinstance(token, str):
            raise ValueError(f"Invalid weekday token: {token!r}")
        if token.isdigit():
            val = int(token)
            if val > 6:
                raise ValueError(f"Weekday integer out of range: {token}")
            return cls(day=DayOfWeek.from_int(val).value)

        const = token[-2:].lower()
        try:
            day_enum = DayOfWeek(const)
        except ValueError as exc:
            raise ValueError(f"Invalid weekday constant: {token!r}") from exc

        nth_str = token[:-2]
        if not nth_str:
            return cls(day=day_enum.value)
        nth = int(nth_str)
        return cls(day=day_enum.value, nth_of_period=nth)


@dataclass
class RecurrenceRule:
    """
    RFC 8984 Section 4.3.3 ``RecurrenceRule`` data type.

    Represents a recurrence rule in JSCalendar format and provides occurrence
    expansion, validation, and conversion to/from ``dateutil.rrule.rrule``.
    """

    frequency: str | int
    interval: int = 1
    rscale: str = "gregorian"
    skip: str = "omit"
    first_day_of_week: str | int | None = "mo"
    by_day: tuple[NDay, ...] = ()
    by_month_day: tuple[int, ...] = ()
    by_month: tuple[str, ...] = ()
    by_year_day: tuple[int, ...] = ()
    by_week_no: tuple[int, ...] = ()
    by_hour: tuple[int, ...] = ()
    by_minute: tuple[int, ...] = ()
    by_second: tuple[int, ...] = ()
    by_set_position: tuple[int, ...] = ()
    count: int | None = None
    until: datetime.datetime | None = None

    def __init__(
        self,
        frequency: str | int | Frequency,
        interval: int = 1,
        rscale: str = "gregorian",
        skip: str | Skip = "omit",
        first_day_of_week: str | int | DayOfWeek | NDay | None = "mo",
        by_day: Iterable[NDay | str | int | Any] = (),
        by_month_day: Iterable[int] = (),
        by_month: Iterable[str | int] = (),
        by_year_day: Iterable[int] = (),
        by_week_no: Iterable[int] = (),
        by_hour: Iterable[int] = (),
        by_minute: Iterable[int] = (),
        by_second: Iterable[int] = (),
        by_set_position: Iterable[int] = (),
        count: int | None = None,
        until: datetime.datetime | None = None,
    ) -> None:
        if isinstance(frequency, Frequency):
            self.frequency = frequency.value
        elif isinstance(frequency, int) and not isinstance(frequency, bool):
            if 0 <= frequency < len(_FREQUENCIES_BY_INDEX):
                self.frequency = _FREQUENCIES_BY_INDEX[frequency].value
            else:
                self.frequency = frequency  # kept so validate() reports exact invalid value
        elif isinstance(frequency, str):
            self.frequency = frequency.lower().strip()
        else:
            self.frequency = frequency

        self.interval = interval
        self.rscale = rscale.lower().strip() if isinstance(rscale, str) else rscale
        self.skip = (
            skip.value
            if isinstance(skip, Skip)
            else (skip.lower().strip() if isinstance(skip, str) else skip)
        )

        if first_day_of_week is None:
            self.first_day_of_week = "mo"
        elif isinstance(first_day_of_week, DayOfWeek):
            self.first_day_of_week = first_day_of_week.value
        elif isinstance(first_day_of_week, NDay):
            self.first_day_of_week = first_day_of_week.day
        elif hasattr(first_day_of_week, "number"):
            self.first_day_of_week = DayOfWeek.from_int(int(first_day_of_week.number)).value
        elif isinstance(first_day_of_week, int) and not isinstance(first_day_of_week, bool):
            if 0 <= first_day_of_week <= 6:
                self.first_day_of_week = DayOfWeek.from_int(first_day_of_week).value
            else:
                self.first_day_of_week = first_day_of_week
        elif isinstance(first_day_of_week, str):
            self.first_day_of_week = first_day_of_week.lower().strip()
        else:
            self.first_day_of_week = first_day_of_week

        self.by_day = self._normalize_by_day(by_day)
        self.by_month_day = self._normalize_int_tuple(by_month_day)
        self.by_month = self._normalize_by_month(by_month)
        self.by_year_day = self._normalize_int_tuple(by_year_day)
        self.by_week_no = self._normalize_int_tuple(by_week_no)
        self.by_hour = self._normalize_int_tuple(by_hour)
        self.by_minute = self._normalize_int_tuple(by_minute)
        self.by_second = self._normalize_int_tuple(by_second)
        self.by_set_position = self._normalize_int_tuple(by_set_position)
        self.count = count
        self.until = until

    @staticmethod
    def _normalize_by_day(values: Any) -> tuple[NDay, ...]:
        if values is None:
            return ()
        if isinstance(values, (str, NDay)) or not hasattr(values, "__iter__"):
            items = [values]
        else:
            items = list(values)
        normalized: list[NDay] = []
        for item in items:
            if isinstance(item, NDay):
                normalized.append(item)
            elif hasattr(item, "number") and hasattr(item, "index"):
                normalized.append(
                    NDay(day=DayOfWeek.from_int(int(item.number)).value, nth_of_period=item.index)
                )
            elif isinstance(item, Mapping):
                normalized.append(NDay.from_jscalendar(item))
            else:
                normalized.append(NDay.from_icalendar(item))
        return tuple(normalized)

    @staticmethod
    def _normalize_int_tuple(values: Any) -> tuple[int, ...]:
        if values is None:
            return ()
        if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
            items = [values]
        else:
            items = list(values)
        return tuple(int(v) if not isinstance(v, bool) else v for v in items)

    @staticmethod
    def _normalize_by_month(values: Any) -> tuple[str, ...]:
        if values is None:
            return ()
        if isinstance(values, str) or not hasattr(values, "__iter__"):
            items = [values]
        else:
            items = list(values)
        return tuple(str(v).upper().strip() for v in items)

    def validate(self, strict_rfc8984: bool = True) -> None:
        """
        Validate all properties of this ``RecurrenceRule`` against RFC 8984 §4.3.3.
        """
        try:
            Frequency(self.frequency)
        except ValueError as exc:
            raise exceptions.ValidationError(f"invalid freq parameter: {self.frequency!r}") from exc

        if isinstance(self.interval, bool):
            raise exceptions.ValidationError(f"invalid interval parameter: {self.interval!r}")
        try:
            interval_int = int(self.interval)
            if interval_int < 1:
                raise ValueError
        except (ValueError, TypeError) as exc:
            raise exceptions.ValidationError(
                f"invalid interval parameter: {self.interval!r}"
            ) from exc

        if not isinstance(self.rscale, str) or not self.rscale:
            raise exceptions.ValidationError(f"invalid rscale parameter: {self.rscale!r}")

        try:
            Skip(self.skip)
        except ValueError as exc:
            raise exceptions.ValidationError(f"invalid skip parameter: {self.skip!r}") from exc

        if self.first_day_of_week is not None:
            try:
                DayOfWeek(str(self.first_day_of_week).lower())
            except ValueError as exc:
                raise exceptions.ValidationError(
                    f"invalide wkst parameter: {self.first_day_of_week!r}"
                ) from exc

        if self.until is not None and not isinstance(self.until, datetime.datetime):
            raise exceptions.ValidationError(f"invalid datetime: {self.until!r}")

        if self.count is not None:
            if isinstance(self.count, bool):
                raise exceptions.ValidationError(f"invalid count parameter: {self.count!r}")
            try:
                count_int = int(self.count)
                if strict_rfc8984 and count_int < 1:
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise exceptions.ValidationError(
                    f"invalid count parameter: {self.count!r}"
                ) from exc

        if strict_rfc8984 and self.count is not None and self.until is not None:
            raise exceptions.ValidationError(
                "count and until cannot both be specified in an RFC 8984 RecurrenceRule"
            )

        for nday in self.by_day:
            if not isinstance(nday, NDay):
                raise exceptions.ValidationError(f"invalid byday parameter: {nday!r}")
            nday.validate()

        for m_str in self.by_month:
            if not isinstance(m_str, str):
                raise exceptions.ValidationError(f"invalid bymonth parameter: {m_str!r}")
            m_clean = m_str[:-1] if (m_str.endswith("L") and self.rscale != "gregorian") else m_str
            try:
                m_int = int(m_clean)
                max_month = 12 if self.rscale == "gregorian" else 13
                if not (1 <= m_int <= max_month):
                    raise ValueError
            except ValueError as exc:
                raise exceptions.ValidationError(f"invalid bymonth parameter: {m_str!r}") from exc

        self._validate_int_seq(
            "bymonthday", self.by_month_day, -31, 31, disallow_zero=strict_rfc8984
        )
        self._validate_int_seq(
            "byyearday", self.by_year_day, -366, 366, disallow_zero=strict_rfc8984
        )
        self._validate_int_seq("byweekno", self.by_week_no, -53, 53, disallow_zero=strict_rfc8984)
        self._validate_int_seq("byhour", self.by_hour, 0, 23, disallow_zero=False)
        self._validate_int_seq("byminute", self.by_minute, 0, 59, disallow_zero=False)
        self._validate_int_seq("bysecond", self.by_second, 0, 60, disallow_zero=False)
        self._validate_int_seq(
            "bysetpos", self.by_set_position, -366, 366, disallow_zero=strict_rfc8984
        )

    @staticmethod
    def _validate_int_seq(
        param: str,
        values: Sequence[Any],
        min_value: int,
        max_value: int,
        disallow_zero: bool = True,
    ) -> None:
        for val in values:
            if isinstance(val, bool):
                raise exceptions.ValidationError(f"invalid {param} parameter: {val!r}")
            try:
                iv = int(val)
                if iv < min_value or iv > max_value or (disallow_zero and iv == 0):
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise exceptions.ValidationError(f"invalid {param} parameter: {val!r}") from exc

    def to_jscalendar(
        self, include_defaults: bool = False, *, time_zone: datetime.tzinfo | None = None
    ) -> dict[str, Any]:
        """Serialize this ``RecurrenceRule`` to an RFC 8984 JSON-compatible dictionary."""
        try:
            self.validate(strict_rfc8984=False)
        except exceptions.ValidationError as exc:
            raise exceptions.SerializationError(str(exc.args[0])) from exc

        data: dict[str, Any] = {
            "@type": "RecurrenceRule",
            "frequency": str(self.frequency),
        }
        if include_defaults or int(self.interval) != 1:
            data["interval"] = int(self.interval)
        if include_defaults or self.rscale != "gregorian":
            data["rscale"] = self.rscale
        if include_defaults or self.skip != "omit":
            data["skip"] = self.skip
        if include_defaults or (self.first_day_of_week and self.first_day_of_week != "mo"):
            data["firstDayOfWeek"] = str(self.first_day_of_week)

        if self.by_day:
            data["byDay"] = [nday.to_jscalendar() for nday in self.by_day]
        if self.by_month_day:
            data["byMonthDay"] = [int(d) for d in self.by_month_day]
        if self.by_month:
            data["byMonth"] = [str(m) for m in self.by_month]
        if self.by_year_day:
            data["byYearDay"] = [int(d) for d in self.by_year_day]
        if self.by_week_no:
            data["byWeekNo"] = [int(w) for w in self.by_week_no]
        if self.by_hour:
            data["byHour"] = [int(h) for h in self.by_hour]
        if self.by_minute:
            data["byMinute"] = [int(m) for m in self.by_minute]
        if self.by_second:
            data["bySecond"] = [int(s) for s in self.by_second]
        if self.by_set_position:
            data["bySetPosition"] = [int(p) for p in self.by_set_position]

        if self.count is not None:
            data["count"] = int(self.count)
        elif self.until is not None:
            data["until"] = format_local_datetime(self.until, time_zone)

        return data

    @classmethod
    def from_jscalendar(
        cls, data: Mapping[str, Any], *, time_zone: datetime.tzinfo | None = None
    ) -> RecurrenceRule:
        """Deserialize an RFC 8984 ``RecurrenceRule`` dictionary."""
        if not isinstance(data, Mapping):
            raise exceptions.DeserializationError(f"Expected RecurrenceRule dict, got {data!r}")

        obj_type = data.get("@type")
        if obj_type is not None and obj_type != "RecurrenceRule":
            raise exceptions.DeserializationError(f"Invalid RecurrenceRule @type: {obj_type!r}")

        allowed_keys = {
            "@type",
            "frequency",
            "interval",
            "rscale",
            "skip",
            "firstDayOfWeek",
            "byDay",
            "byMonthDay",
            "byMonth",
            "byYearDay",
            "byWeekNo",
            "byHour",
            "byMinute",
            "bySecond",
            "bySetPosition",
            "count",
            "until",
        }
        unknown_keys = set(data.keys()) - allowed_keys
        if unknown_keys:
            raise exceptions.DeserializationError(
                f"Unknown RecurrenceRule properties: {sorted(unknown_keys)}"
            )

        if "frequency" not in data or not isinstance(data["frequency"], str):
            raise exceptions.DeserializationError(
                "Missing or invalid 'frequency' in RecurrenceRule"
            )

        until_val = data.get("until")
        until_dt = (
            parse_jscalendar_datetime(until_val, local=True, time_zone=time_zone)
            if until_val is not None
            else None
        )

        by_day_raw = data.get("byDay") or ()
        if not isinstance(by_day_raw, list | tuple):
            raise exceptions.DeserializationError(f"Invalid byDay list: {by_day_raw!r}")
        by_day = tuple(NDay.from_jscalendar(item) for item in by_day_raw)

        def _parse_int_list(key: str) -> tuple[int, ...]:
            raw = data.get(key)
            if raw is None:
                return ()
            if not isinstance(raw, list | tuple) or not raw:
                raise exceptions.DeserializationError(f"Invalid {key} list: {raw!r}")
            res: list[int] = []
            for item in raw:
                if isinstance(item, bool) or not isinstance(item, int):
                    raise exceptions.DeserializationError(f"Invalid integer in {key}: {item!r}")
                res.append(item)
            return tuple(res)

        by_month_raw = data.get("byMonth")
        by_month: tuple[str, ...] = ()
        if by_month_raw is not None:
            if not isinstance(by_month_raw, list | tuple) or not by_month_raw:
                raise exceptions.DeserializationError(f"Invalid byMonth list: {by_month_raw!r}")
            for item in by_month_raw:
                if not isinstance(item, str):
                    raise exceptions.DeserializationError(
                        f"RFC 8984 byMonth values must be strings, got {item!r}"
                    )
            by_month = tuple(by_month_raw)

        interval_raw = data.get("interval", 1)
        if isinstance(interval_raw, bool) or not isinstance(interval_raw, int):
            raise exceptions.DeserializationError(f"Invalid interval: {interval_raw!r}")

        count_raw = data.get("count")
        if count_raw is not None and (
            isinstance(count_raw, bool) or not isinstance(count_raw, int)
        ):
            raise exceptions.DeserializationError(f"Invalid count: {count_raw!r}")

        try:
            rule = cls(
                frequency=data["frequency"],
                interval=interval_raw,
                rscale=data.get("rscale", "gregorian"),
                skip=data.get("skip", "omit"),
                first_day_of_week=data.get("firstDayOfWeek", "mo"),
                by_day=by_day,
                by_month_day=_parse_int_list("byMonthDay"),
                by_month=by_month,
                by_year_day=_parse_int_list("byYearDay"),
                by_week_no=_parse_int_list("byWeekNo"),
                by_hour=_parse_int_list("byHour"),
                by_minute=_parse_int_list("byMinute"),
                by_second=_parse_int_list("bySecond"),
                by_set_position=_parse_int_list("bySetPosition"),
                count=count_raw,
                until=until_dt,
            )
            rule.validate(strict_rfc8984=True)
        except exceptions.ValidationError as exc:
            raise exceptions.DeserializationError(str(exc.args[0])) from exc

        return rule

    def to_text(self, short: bool = False) -> str:
        """Render the rule as natural language text."""
        from django_recur.text import rule_to_text

        return rule_to_text(self, short=short)

    def to_dateutil_rrule(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> dateutil.rrule.rrule:
        """
        Convert this ``RecurrenceRule`` to a ``dateutil.rrule.rrule`` instance.

        Note: If ``skip`` is ``"backward"`` or ``"forward"``, use ``expand_with_skip``
        or ``JSCalendarRecurrence`` which applies RFC 8984 / RFC 7529 skip shifting.
        """
        if self.rscale != "gregorian":
            raise exceptions.UnsupportedFeatureError(
                f"Non-Gregorian rscale {self.rscale!r} cannot be expanded by dateutil.rrule"
            )
        if self._needs_skip_expansion():
            raise exceptions.UnsupportedFeatureError("Use expand_with_skip for SKIP rules")

        freq_int: Any = Frequency(self.frequency).to_int()
        wkst_int = (
            DayOfWeek(str(self.first_day_of_week)).to_int() if self.first_day_of_week else None
        )

        byweekday = [
            dateutil.rrule.weekday(nd.number, nd.nth_of_period)
            if nd.nth_of_period
            else dateutil.rrule.weekday(nd.number)
            for nd in self.by_day
        ] or None

        if 60 in self.by_second:
            raise exceptions.UnsupportedFeatureError(
                "Leap-second occurrences cannot be expanded by Python datetime"
            )
        bymonth = [int(m) for m in self.by_month] if self.by_month else None

        until = self.until
        if until:
            until = normalize_offset_awareness(until, dtstart)
            if dtend and until > dtend:
                until = dtend
        elif dtend:
            until = dtend

        return dateutil.rrule.rrule(
            freq=freq_int,
            dtstart=dtstart,
            interval=int(self.interval),
            wkst=wkst_int,
            count=self.count,
            until=until,
            bysetpos=list(self.by_set_position) or None,
            bymonth=bymonth,
            bymonthday=list(self.by_month_day) or None,
            byyearday=list(self.by_year_day) or None,
            byweekno=list(self.by_week_no) or None,
            byweekday=byweekday,
            byhour=list(self.by_hour) or None,
            byminute=list(self.by_minute) or None,
            bysecond=list(self.by_second) or None,
            cache=cache,
        )

    def _needs_skip_expansion(self) -> bool:
        return self.skip in (Skip.BACKWARD.value, Skip.FORWARD.value) and self.frequency in (
            Frequency.YEARLY.value,
            Frequency.MONTHLY.value,
        )

    def expand_with_skip(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
    ) -> list[datetime.datetime]:
        """Expand a Gregorian SKIP rule into a list of occurrences."""
        return list(self._iter_with_skip(dtstart, dtend))

    def _iter_with_skip(
        self, dtstart: datetime.datetime | None, dtend: datetime.datetime | None
    ) -> Iterator[datetime.datetime]:
        if self.rscale != "gregorian" or any(
            (
                self.by_day,
                self.by_week_no,
                self.by_year_day,
                self.by_hour,
                self.by_minute,
                self.by_second,
                self.by_set_position,
            )
        ):
            raise exceptions.UnsupportedFeatureError(
                "SKIP expansion supports Gregorian month and month-day filters only"
            )
        base_start = dtstart or datetime.datetime.now()
        until = self.until
        if until:
            until = normalize_offset_awareness(until, base_start)
            if dtend and until > dtend:
                until = dtend
        elif dtend:
            until = dtend

        count = 0
        last = None

        months_filter = [int(m) for m in self.by_month] if self.by_month else None
        month_days = self.by_month_day or (base_start.day,)
        step = int(self.interval)

        year = base_start.year
        month = base_start.month

        while year <= datetime.MAXYEAR:
            if self.frequency == Frequency.YEARLY.value:
                target_months = months_filter or [base_start.month]
            else:
                target_months = [month]
                if months_filter and month not in months_filter:
                    target_months = []

            candidates: set[datetime.datetime] = set()
            for m in target_months:
                _, max_day = calendar.monthrange(year, m)
                for req_day in month_days:
                    actual_day = req_day if req_day > 0 else max_day + 1 + req_day
                    if 1 <= actual_day <= max_day:
                        cand = base_start.replace(year=year, month=m, day=actual_day)
                    else:
                        if self.skip == Skip.BACKWARD.value:
                            cand = base_start.replace(year=year, month=m, day=max_day)
                        elif self.skip == Skip.FORWARD.value:
                            next_y, next_m = (year + 1, 1) if m == 12 else (year, m + 1)
                            if next_y > datetime.MAXYEAR:
                                continue
                            cand = base_start.replace(year=next_y, month=next_m, day=1)
                        else:
                            continue
                    candidates.add(cand)

            for cand in sorted(candidates):
                if cand < base_start or cand == last:
                    continue
                if until and cand > until:
                    return
                yield cand
                last = cand
                count += 1
                if self.count is not None and count >= self.count:
                    return

            if self.frequency == Frequency.YEARLY.value:
                year += step
            else:
                total_m = (year * 12 + (month - 1)) + step
                year, month = divmod(total_m, 12)
                month += 1
            if until:
                first_month = (
                    min(months_filter or [base_start.month])
                    if self.frequency == "yearly"
                    else month
                )
                if year > until.year or (year == until.year and first_month > until.month):
                    break


class _SkipOccurrences:
    """Repeatable iterable for dateutil's ordered recurrence merge."""

    def __init__(
        self,
        rule: RecurrenceRule,
        dtstart: datetime.datetime | None,
        dtend: datetime.datetime | None,
    ) -> None:
        self.rule = rule
        self.dtstart = dtstart if dtstart is not None else datetime.datetime.now()
        self.dtend = dtend

    def __iter__(self) -> Iterator[datetime.datetime]:
        return self.rule._iter_with_skip(self.dtstart, self.dtend)


@dataclass
class RecurrenceOverride:
    """
    RFC 8984 ``recurrenceOverrides`` entry (``PatchObject``).

    - ``excluded=True`` corresponds to an excluded occurrence (RFC 5545 ``EXDATE``).
    - ``excluded=False`` with empty ``patches`` corresponds to an included occurrence (RFC 5545 ``RDATE``).
    - ``patches`` holds any RFC 8984 property overrides for that specific occurrence.
    """

    excluded: bool = False
    patches: dict[str, Any] = field(default_factory=dict)

    def to_jscalendar(self) -> dict[str, Any]:
        if self.excluded:
            return {"excluded": True, **self.patches}
        return dict(self.patches)

    @classmethod
    def from_jscalendar(cls, data: Mapping[str, Any]) -> RecurrenceOverride:
        if not isinstance(data, Mapping):
            raise exceptions.DeserializationError(
                f"Invalid recurrenceOverrides PatchObject: {data!r}"
            )
        excluded = bool(data.get("excluded", False))
        patches = {k: v for k, v in data.items() if k != "excluded"}
        return cls(excluded=excluded, patches=patches)


class JSCalendarRecurrence:
    """
    Complete RFC 8984 recurrence schedule representation.

    Combines ``start`` (``dtstart``), ``dtend``, ``timeZone``, ``recurrenceRules``,
    ``excludedRecurrenceRules``, and ``recurrenceOverrides`` (which unifies ``RDATE``,
    ``EXDATE``, and instance patch objects).
    """

    def __init__(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        recurrence_rules: Iterable[RecurrenceRule] = (),
        excluded_recurrence_rules: Iterable[RecurrenceRule] = (),
        recurrence_overrides: Mapping[datetime.datetime, RecurrenceOverride] | None = None,
        rdates: Iterable[datetime.datetime] = (),
        exdates: Iterable[datetime.datetime] = (),
        time_zone: str | None = None,
        include_dtstart: bool = True,
        *,
        start: datetime.datetime | None = None,
    ) -> None:
        self._cache: dict[Any, dateutil.rrule.rruleset] = {}
        self.dtstart = dtstart if dtstart is not None else start
        self.dtend = dtend
        self.time_zone = time_zone
        self.include_dtstart = include_dtstart

        self.recurrence_rules: list[RecurrenceRule] = list(recurrence_rules)
        self.excluded_recurrence_rules: list[RecurrenceRule] = list(excluded_recurrence_rules)

        self.recurrence_overrides: dict[datetime.datetime, RecurrenceOverride] = (
            dict(recurrence_overrides) if recurrence_overrides else {}
        )
        for rdate in rdates:
            self.recurrence_overrides[rdate] = RecurrenceOverride(excluded=False)
        for exdate in exdates:
            self.recurrence_overrides[exdate] = RecurrenceOverride(excluded=True)

    @property
    def start(self) -> datetime.datetime | None:
        return self.dtstart

    @start.setter
    def start(self, value: datetime.datetime | None) -> None:
        self.dtstart = value

    @property
    def rrules(self) -> list[RecurrenceRule]:
        return self.recurrence_rules

    @rrules.setter
    def rrules(self, value: Iterable[RecurrenceRule]) -> None:
        self.recurrence_rules = list(value)

    @property
    def exrules(self) -> list[RecurrenceRule]:
        return self.excluded_recurrence_rules

    @exrules.setter
    def exrules(self, value: Iterable[RecurrenceRule]) -> None:
        self.excluded_recurrence_rules = list(value)

    @property
    def rdates(self) -> list[datetime.datetime]:
        return [dt for dt, ov in self.recurrence_overrides.items() if not ov.excluded]

    @rdates.setter
    def rdates(self, value: Iterable[datetime.datetime]) -> None:
        ex = {dt: ov for dt, ov in self.recurrence_overrides.items() if ov.excluded}
        for dt in value:
            ex[dt] = RecurrenceOverride(excluded=False)
        self.recurrence_overrides = ex

    @property
    def exdates(self) -> list[datetime.datetime]:
        return [dt for dt, ov in self.recurrence_overrides.items() if ov.excluded]

    @exdates.setter
    def exdates(self, value: Iterable[datetime.datetime]) -> None:
        inc = {dt: ov for dt, ov in self.recurrence_overrides.items() if not ov.excluded}
        for dt in value:
            inc[dt] = RecurrenceOverride(excluded=True)
        self.recurrence_overrides = inc

    def validate(self, strict_rfc8984: bool = True) -> None:
        if self.dtstart is not None and not isinstance(self.dtstart, datetime.datetime):
            raise exceptions.ValidationError(f"invalid datetime: {self.dtstart!r}")
        if self.dtend is not None and not isinstance(self.dtend, datetime.datetime):
            raise exceptions.ValidationError(f"invalid datetime: {self.dtend!r}")

        for rule in self.recurrence_rules:
            if not isinstance(rule, RecurrenceRule):
                raise exceptions.ValidationError(f"invalid RecurrenceRule: {rule!r}")
            rule.validate(strict_rfc8984=strict_rfc8984)

        for exrule in self.excluded_recurrence_rules:
            if not isinstance(exrule, RecurrenceRule):
                raise exceptions.ValidationError(f"invalid excluded RecurrenceRule: {exrule!r}")
            exrule.validate(strict_rfc8984=strict_rfc8984)

        for dt, ov in self.recurrence_overrides.items():
            if not isinstance(dt, datetime.datetime):
                raise exceptions.ValidationError(f"invalid datetime: {dt!r}")
            if not isinstance(ov, RecurrenceOverride):
                raise exceptions.ValidationError(f"invalid RecurrenceOverride: {ov!r}")

    def _serialization_time_zone(self) -> str | None:
        if self.time_zone is not None:
            return self.time_zone
        dates = (
            self.dtstart,
            self.dtend,
            *self.recurrence_overrides,
            *(rule.until for rule in (*self.rrules, *self.exrules)),
        )
        aware = next((date for date in dates if date is not None and is_aware(date)), None)
        if aware is None:
            return None
        return getattr(aware.tzinfo, "key", None) or getattr(aware.tzinfo, "zone", None) or "UTC"

    def to_jscalendar(self, include_defaults: bool = False) -> dict[str, Any]:
        """Serialize the schedule to a JSCalendar recurrence object."""
        try:
            self.validate(strict_rfc8984=False)
        except exceptions.ValidationError as exc:
            raise exceptions.SerializationError(str(exc.args[0])) from exc

        zone_name = self._serialization_time_zone()
        zone = calendar_time_zone(zone_name) if zone_name is not None else None
        result: dict[str, Any] = {"@type": "Event"}
        if self.dtstart is not None:
            result["start"] = format_local_datetime(self.dtstart, zone)
        if self.dtend is not None:
            result["dtend"] = format_local_datetime(self.dtend, zone)
        if zone_name is not None:
            result["timeZone"] = zone_name
        if not self.include_dtstart:
            result["includeDtstart"] = False

        if self.recurrence_rules:
            result["recurrenceRules"] = [
                r.to_jscalendar(include_defaults=include_defaults, time_zone=zone)
                for r in self.recurrence_rules
            ]
        if self.excluded_recurrence_rules:
            result["excludedRecurrenceRules"] = [
                r.to_jscalendar(include_defaults=include_defaults, time_zone=zone)
                for r in self.excluded_recurrence_rules
            ]
        if self.recurrence_overrides:
            overrides_dict: dict[str, dict[str, Any]] = {}
            for dt, ov in self.recurrence_overrides.items():
                key = format_local_datetime(dt, zone)
                overrides_dict[key] = ov.to_jscalendar()
            result["recurrenceOverrides"] = overrides_dict

        return result

    def to_json(self, indent: int | None = None, include_defaults: bool = False) -> str:
        return json.dumps(self.to_jscalendar(include_defaults=include_defaults), indent=indent)

    @classmethod
    def from_jscalendar(
        cls,
        data: Mapping[str, Any] | str,
        include_dtstart: bool = True,
    ) -> JSCalendarRecurrence:
        """
        Deserialize an RFC 8984 JSCalendar dictionary or JSON string into a
        ``JSCalendarRecurrence``.
        """
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError as exc:
                raise exceptions.DeserializationError(f"Malformed JSCalendar JSON: {exc}") from exc
            if not isinstance(parsed, Mapping):
                raise exceptions.DeserializationError("JSCalendar JSON root must be an object")
            data = parsed

        if not isinstance(data, Mapping):
            raise exceptions.DeserializationError(f"Expected JSCalendar mapping, got {data!r}")

        # Also allow a standalone RecurrenceRule object at root
        if data.get("@type") == "RecurrenceRule" or (
            "frequency" in data and "recurrenceRules" not in data
        ):
            single_rule = RecurrenceRule.from_jscalendar(data)
            return cls(recurrence_rules=[single_rule], include_dtstart=include_dtstart)

        time_zone = data.get("timeZone")
        if "timeZone" not in data:
            # Earlier versions wrote UTC timestamps without a timeZone property.
            dates = (data.get("start"), data.get("dtend"))
            if any(isinstance(value, str) and value.upper().endswith("Z") for value in dates):
                time_zone = "UTC"
        zone = calendar_time_zone(time_zone) if time_zone is not None else None
        dtstart = (
            parse_jscalendar_datetime(data["start"], local=True, time_zone=zone)
            if "start" in data and data["start"] is not None
            else None
        )
        dtend = (
            parse_jscalendar_datetime(data["dtend"], local=True, time_zone=zone)
            if "dtend" in data and data["dtend"] is not None
            else None
        )
        eff_include_dtstart = bool(data.get("includeDtstart", include_dtstart))

        rrules_raw = data.get("recurrenceRules") or []
        if not isinstance(rrules_raw, list | tuple):
            raise exceptions.DeserializationError("recurrenceRules must be a list")
        rrules = [RecurrenceRule.from_jscalendar(r, time_zone=zone) for r in rrules_raw]

        exrules_raw = data.get("excludedRecurrenceRules") or []
        if not isinstance(exrules_raw, list | tuple):
            raise exceptions.DeserializationError("excludedRecurrenceRules must be a list")
        exrules = [RecurrenceRule.from_jscalendar(r, time_zone=zone) for r in exrules_raw]

        overrides_raw = data.get("recurrenceOverrides") or {}
        if not isinstance(overrides_raw, Mapping):
            raise exceptions.DeserializationError("recurrenceOverrides must be an object")
        overrides: dict[datetime.datetime, RecurrenceOverride] = {}
        for dt_str, patch_obj in overrides_raw.items():
            dt_val = parse_jscalendar_datetime(dt_str, local=True, time_zone=zone)
            overrides[dt_val] = RecurrenceOverride.from_jscalendar(patch_obj)

        return cls(
            dtstart=dtstart,
            dtend=dtend,
            recurrence_rules=rrules,
            excluded_recurrence_rules=exrules,
            recurrence_overrides=overrides,
            time_zone=time_zone,
            include_dtstart=eff_include_dtstart,
        )

    from_json = from_jscalendar

    def to_icalendar(self) -> str:
        from django_recur.rfc5545 import jscalendar_to_icalendar

        return jscalendar_to_icalendar(self)

    @classmethod
    def from_icalendar(cls, text: str, include_dtstart: bool = True) -> JSCalendarRecurrence:
        from django_recur.rfc5545 import icalendar_to_jscalendar

        return icalendar_to_jscalendar(text, include_dtstart=include_dtstart)

    def to_dateutil_rruleset(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> dateutil.rrule.rruleset:
        eff_dtstart = dtstart or self.dtstart
        eff_dtend = dtend or self.dtend
        if self.time_zone is not None and deserialize_tz_enabled():
            zone = calendar_time_zone(self.time_zone)
            if eff_dtstart is not None and is_naive(eff_dtstart):
                eff_dtstart = make_aware(eff_dtstart, zone)
            if eff_dtend is not None and is_naive(eff_dtend):
                eff_dtend = make_aware(eff_dtend, zone)

        if eff_dtend:
            eff_dtend = normalize_offset_awareness(eff_dtend, eff_dtstart)

        if cache:
            cached = self._cache.get((eff_dtstart, eff_dtend))
            if cached is not None:
                return cached

        rruleset = dateutil.rrule.rruleset(cache=cache)

        for rrule in self.recurrence_rules:
            if rrule._needs_skip_expansion():
                # dateutil merges any sorted, repeatable iterable of datetimes.
                rruleset.rrule(_SkipOccurrences(rrule, eff_dtstart, eff_dtend))  # type: ignore[arg-type]
            else:
                rruleset.rrule(rrule.to_dateutil_rrule(eff_dtstart, eff_dtend, cache))

        for exrule in self.excluded_recurrence_rules:
            if exrule._needs_skip_expansion():
                rruleset.exrule(_SkipOccurrences(exrule, eff_dtstart, eff_dtend))  # type: ignore[arg-type]
            else:
                rruleset.exrule(exrule.to_dateutil_rrule(eff_dtstart, eff_dtend, cache))

        if self.include_dtstart and eff_dtstart is not None:
            rruleset.rdate(eff_dtstart)

        for rdate in self.rdates:
            norm_rdate = normalize_offset_awareness(rdate, eff_dtstart)
            if eff_dtend is None or norm_rdate < eff_dtend:
                rruleset.rdate(norm_rdate)

        if eff_dtend is not None:
            rruleset.rdate(eff_dtend)

        for exdate in self.exdates:
            norm_exdate = normalize_offset_awareness(exdate, eff_dtstart)
            if eff_dtend is None or norm_exdate < eff_dtend:
                rruleset.exdate(norm_exdate)

        if cache:
            self._cache[(eff_dtstart, eff_dtend)] = rruleset

        return rruleset

    def occurrences(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> dateutil.rrule.rruleset:
        return self.to_dateutil_rruleset(dtstart=dtstart, dtend=dtend, cache=cache)

    def count(
        self,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> int:
        return int(
            self.to_dateutil_rruleset(dtstart=dtstart, dtend=dtend, cache=cache).count() or 0
        )

    def before(
        self,
        dt: datetime.datetime,
        inc: bool = False,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> datetime.datetime | None:
        return self.to_dateutil_rruleset(dtstart=dtstart, dtend=dtend, cache=cache).before(dt, inc)

    def after(
        self,
        dt: datetime.datetime,
        inc: bool = False,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> datetime.datetime | None:
        return self.to_dateutil_rruleset(dtstart=dtstart, dtend=dtend, cache=cache).after(dt, inc)

    def between(
        self,
        after: datetime.datetime,
        before: datetime.datetime,
        inc: bool = False,
        dtstart: datetime.datetime | None = None,
        dtend: datetime.datetime | None = None,
        cache: bool = False,
    ) -> list[datetime.datetime]:
        return list(
            self.to_dateutil_rruleset(dtstart=dtstart, dtend=dtend, cache=cache).between(
                after, before, inc
            )
        )

    def __iter__(self) -> Iterator[datetime.datetime]:
        return iter(self.occurrences())

    def __bool__(self) -> bool:
        return bool(
            self.dtstart
            or self.dtend
            or self.recurrence_rules
            or self.excluded_recurrence_rules
            or self.recurrence_overrides
        )

    def __hash__(self) -> int:
        overrides_tuple = tuple(
            (dt, ov.excluded, tuple(sorted(ov.patches.items())))
            for dt, ov in self.recurrence_overrides.items()
        )
        return hash(
            (
                self.dtstart,
                self.dtend,
                tuple(self.recurrence_rules),
                tuple(self.excluded_recurrence_rules),
                overrides_tuple,
            )
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JSCalendarRecurrence):
            return False
        return (
            self.dtstart == other.dtstart
            and self.dtend == other.dtend
            and self.recurrence_rules == other.recurrence_rules
            and self.excluded_recurrence_rules == other.excluded_recurrence_rules
            and self.recurrence_overrides == other.recurrence_overrides
        )

    def __str__(self) -> str:
        return self.to_json()
