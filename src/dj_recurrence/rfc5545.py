"""
RFC 5545 (iCalendar) & RFC 2445 parser, serializer, and bidirectional mapper
to/from RFC 8984 (JSCalendar), including the programmatic Feature & Auto-Mapping Matrix.
"""

from __future__ import annotations

import datetime
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from dateutil import tz
from django.utils.timezone import get_current_timezone

from dj_recurrence import exceptions
from dj_recurrence.rfc8984 import (
    Frequency,
    JSCalendarRecurrence,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    Skip,
    deserialize_tz_enabled,
    to_utc,
)


@dataclass(frozen=True)
class FeatureMatrixEntry:
    """Represents a single capability in the RFC 8984 <-> RFC 5545 feature matrix."""

    feature_id: str
    rfc8984_property: str
    rfc5545_property: str
    rfc8984_implemented: bool
    rfc5545_implemented: bool
    auto_mapping: str  # "lossless" | "conditional" | "lossy"
    notes: str


FEATURE_MATRIX: tuple[FeatureMatrixEntry, ...] = (
    FeatureMatrixEntry(
        feature_id="start_dtstart",
        rfc8984_property="start (LocalDateTime / UTCDateTime)",
        rfc5545_property="DTSTART",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Mapped bidirectionally between JSCalendar 'start' and iCalendar 'DTSTART'.",
    ),
    FeatureMatrixEntry(
        feature_id="end_dtend",
        rfc8984_property="dtend / duration",
        rfc5545_property="DTEND",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Mapped bidirectionally to preserve recurrence window bounds.",
    ),
    FeatureMatrixEntry(
        feature_id="recurrence_rules",
        rfc8984_property="recurrenceRules (RecurrenceRule[])",
        rfc5545_property="RRULE",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="conditional",
        notes=(
            "Single rule is 100% lossless. Multiple recurrenceRules map to multiple RRULE lines "
            "(valid in RFC 2445, deprecated in RFC 5545 §3.8.5.3)."
        ),
    ),
    FeatureMatrixEntry(
        feature_id="excluded_recurrence_rules",
        rfc8984_property="excludedRecurrenceRules (RecurrenceRule[])",
        rfc5545_property="EXRULE (RFC 2445)",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="conditional",
        notes=(
            "First-class in RFC 8984 §4.3.2. Maps to EXRULE (part of RFC 2445, removed in strict "
            "RFC 5545, restored in RFC 8984)."
        ),
    ),
    FeatureMatrixEntry(
        feature_id="frequency",
        rfc8984_property="frequency (yearly..secondly)",
        rfc5545_property="FREQ (YEARLY..SECONDLY)",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Case-normalized 1:1 mapping across all 7 recurrence frequencies.",
    ),
    FeatureMatrixEntry(
        feature_id="interval",
        rfc8984_property="interval (UnsignedInt, default 1)",
        rfc5545_property="INTERVAL (default 1)",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Omitted in canonical output when equal to default 1.",
    ),
    FeatureMatrixEntry(
        feature_id="first_day_of_week",
        rfc8984_property="firstDayOfWeek (mo..su, default 'mo')",
        rfc5545_property="WKST (MO..SU)",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="1:1 mapping between lowercase DayOfWeek and uppercase WKST.",
    ),
    FeatureMatrixEntry(
        feature_id="count_until",
        rfc8984_property="count / until",
        rfc5545_property="COUNT / UNTIL",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Mutually exclusive termination bounds mapped 1:1.",
    ),
    FeatureMatrixEntry(
        feature_id="by_day_nday",
        rfc8984_property="byDay (NDay[]: day + nthOfPeriod)",
        rfc5545_property="BYDAY ([+/-n]MO..SU)",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Structured NDay objects map 1:1 to positional weekday tokens (e.g., -1SU).",
    ),
    FeatureMatrixEntry(
        feature_id="by_month",
        rfc8984_property="byMonth (String[]: '1'..'12', '5L')",
        rfc5545_property="BYMONTH (1..12)",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="conditional",
        notes=(
            "Gregorian months '1'..'12' map losslessly to integers 1..12. "
            "Leap month suffix 'L' requires RFC 7529 RSCALE extension in iCalendar."
        ),
    ),
    FeatureMatrixEntry(
        feature_id="by_month_day",
        rfc8984_property="byMonthDay (Int[]: -31..-1, 1..31)",
        rfc5545_property="BYMONTHDAY",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="1:1 integer array mapping.",
    ),
    FeatureMatrixEntry(
        feature_id="by_year_day",
        rfc8984_property="byYearDay (Int[]: -366..-1, 1..366)",
        rfc5545_property="BYYEARDAY",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="1:1 integer array mapping.",
    ),
    FeatureMatrixEntry(
        feature_id="by_week_no",
        rfc8984_property="byWeekNo (Int[]: -53..-1, 1..53)",
        rfc5545_property="BYWEEKNO",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="1:1 ISO 8601 week number mapping.",
    ),
    FeatureMatrixEntry(
        feature_id="by_hour_minute_second",
        rfc8984_property="byHour / byMinute / bySecond",
        rfc5545_property="BYHOUR / BYMINUTE / BYSECOND",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="1:1 time component array mapping.",
    ),
    FeatureMatrixEntry(
        feature_id="by_set_position",
        rfc8984_property="bySetPosition (Int[])",
        rfc5545_property="BYSETPOS",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="1:1 set position filter mapping.",
    ),
    FeatureMatrixEntry(
        feature_id="rscale_skip",
        rfc8984_property="rscale ('gregorian') & skip ('omit'|'backward'|'forward')",
        rfc5545_property="RSCALE / SKIP (RFC 7529 extension)",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="conditional",
        notes=(
            "Default rscale='gregorian' and skip='omit' map losslessly to standard RFC 5545. "
            "Non-default rscale/skip map to RFC 7529 RSCALE/SKIP parameters when enabled, or emit a "
            "conversion warning in strict RFC 5545 mode."
        ),
    ),
    FeatureMatrixEntry(
        feature_id="rdates_overrides",
        rfc8984_property="recurrenceOverrides[dt] = {}",
        rfc5545_property="RDATE",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Empty PatchObject in recurrenceOverrides maps 1:1 to RDATE.",
    ),
    FeatureMatrixEntry(
        feature_id="exdates_overrides",
        rfc8984_property="recurrenceOverrides[dt] = {'excluded': true}",
        rfc5545_property="EXDATE",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="lossless",
        notes="Excluded PatchObject in recurrenceOverrides maps 1:1 to EXDATE.",
    ),
    FeatureMatrixEntry(
        feature_id="property_patch_overrides",
        rfc8984_property="recurrenceOverrides[dt] = {'title': ..., ...}",
        rfc5545_property="Detached VEVENT with RECURRENCE-ID",
        rfc8984_implemented=True,
        rfc5545_implemented=False,
        auto_mapping="lossy",
        notes=(
            "Non-empty PatchObject property modifications (e.g. overriding title/location of a "
            "single occurrence) cannot be represented in a bare RRULE/RDATE string without full "
            "multi-VEVENT iCalendar containers; date inclusion is preserved with a warning."
        ),
    ),
)


@dataclass(frozen=True)
class ConversionIssue:
    """Represents a warning or lossy feature encountered during RFC conversion."""

    code: str
    message: str
    property_name: str


@dataclass
class ConversionReport:
    """Result of converting between RFC 8984 and RFC 5545 with diagnostic metadata."""

    output: Any
    lossless: bool = True
    issues: list[ConversionIssue] = field(default_factory=list)


def serialize_icalendar_dt(dt: datetime.datetime) -> str:
    """Format a datetime as an RFC 5545 UTC ``YYYYMMDDTHHMMSSZ`` string."""
    utc_dt = to_utc(dt)
    assert utc_dt is not None
    return (
        f"{utc_dt.year:04d}{utc_dt.month:02d}{utc_dt.day:02d}"
        f"T{utc_dt.hour:02d}{utc_dt.minute:02d}{utc_dt.second:02d}Z"
    )


def deserialize_icalendar_dt(text: str) -> datetime.datetime:
    """Parse an RFC 5545 / RFC 2445 ``DATE-TIME`` or ``DATE`` string."""
    cleaned = text.strip()
    try:
        year, month, day = int(cleaned[:4]), int(cleaned[4:6]), int(cleaned[6:8])
    except (ValueError, IndexError) as exc:
        raise exceptions.DeserializationError(f"malformed date-time: {text!r}") from exc

    if "T" in cleaned:
        try:
            hour, minute, second = (
                int(cleaned[9:11]),
                int(cleaned[11:13]),
                int(cleaned[13:15]),
            )
        except (ValueError, IndexError) as exc:
            raise exceptions.DeserializationError(f"malformed date-time: {text!r}") from exc
    else:
        hour, minute, second = 0, 0, 0

    tzinfo = tz.UTC if "Z" in cleaned else get_current_timezone()
    try:
        dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=tzinfo)
    except ValueError as exc:
        raise exceptions.DeserializationError(f"malformed date-time: {text!r}") from exc

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


_BYPARAM_MAPPING: tuple[tuple[str, str], ...] = (
    ("by_set_position", "BYSETPOS"),
    ("by_month", "BYMONTH"),
    ("by_month_day", "BYMONTHDAY"),
    ("by_year_day", "BYYEARDAY"),
    ("by_week_no", "BYWEEKNO"),
    ("by_hour", "BYHOUR"),
    ("by_minute", "BYMINUTE"),
    ("by_second", "BYSECOND"),
)


def convert_jscalendar_to_icalendar_with_report(
    obj: JSCalendarRecurrence | RecurrenceRule,
    include_rscale: bool = False,
    strict: bool = False,
    preserve_explicit_wkst: bool = False,
) -> ConversionReport:
    """
    Convert an RFC 8984 ``JSCalendarRecurrence`` or ``RecurrenceRule`` to an RFC 5545
    string, returning a ``ConversionReport`` detailing any lossy or conditional features.
    """
    issues: list[ConversionIssue] = []
    lossless = True

    if isinstance(obj, RecurrenceRule):
        rec = JSCalendarRecurrence(recurrence_rules=[obj])
    elif isinstance(obj, JSCalendarRecurrence):
        rec = obj
    else:
        raise exceptions.SerializationError(f"incompatible object: {obj!r}")

    try:
        rec.validate(strict_rfc8984=False)
    except exceptions.ValidationError as exc:
        raise exceptions.SerializationError(str(exc.args[0])) from exc

    if len(rec.recurrence_rules) > 1:
        issues.append(
            ConversionIssue(
                code="multiple_rrules",
                message="Multiple recurrenceRules mapped to multiple RRULE properties (deprecated in RFC 5545 §3.8.5.3).",
                property_name="recurrenceRules",
            )
        )

    if rec.excluded_recurrence_rules:
        issues.append(
            ConversionIssue(
                code="exrule_used",
                message="excludedRecurrenceRules mapped to EXRULE (part of RFC 2445, deprecated in strict RFC 5545).",
                property_name="excludedRecurrenceRules",
            )
        )

    def _serialize_rule(rule: RecurrenceRule) -> str:
        nonlocal lossless
        values: list[tuple[str, list[str]]] = []

        if rule.rscale != "gregorian":
            if include_rscale:
                values.append(("RSCALE", [rule.rscale.upper()]))
            else:
                lossless = False
                issues.append(
                    ConversionIssue(
                        code="non_gregorian_rscale_dropped",
                        message=f"Non-Gregorian rscale={rule.rscale!r} requires RFC 7529 RSCALE support.",
                        property_name="rscale",
                    )
                )

        values.append(("FREQ", [str(rule.frequency).upper()]))

        if int(rule.interval) != 1:
            values.append(("INTERVAL", [str(int(rule.interval))]))

        if rule.skip != Skip.OMIT.value:
            if include_rscale:
                values.append(("SKIP", [rule.skip.upper()]))
            else:
                lossless = False
                issues.append(
                    ConversionIssue(
                        code="skip_dropped",
                        message=f"skip={rule.skip!r} requires RFC 7529 SKIP parameter in iCalendar.",
                        property_name="skip",
                    )
                )

        if rule.first_day_of_week and (
            preserve_explicit_wkst or str(rule.first_day_of_week).lower() != "mo"
        ):
            values.append(("WKST", [str(rule.first_day_of_week).upper()]))

        if rule.count is not None and rule.until is not None:
            issues.append(
                ConversionIssue(
                    code="count_and_until_both_set",
                    message="Both count and until were set; only COUNT is serialized.",
                    property_name="until",
                )
            )

        if rule.count is not None:
            values.append(("COUNT", [str(int(rule.count))]))
        elif rule.until is not None:
            values.append(("UNTIL", [serialize_icalendar_dt(rule.until)]))

        if rule.by_day:
            values.append(("BYDAY", [nd.to_icalendar() for nd in rule.by_day]))

        for attr_name, ical_name in _BYPARAM_MAPPING:
            seq = getattr(rule, attr_name, ())
            if seq:
                if attr_name == "by_month":
                    cleaned_months: list[str] = []
                    for m in seq:
                        if str(m).endswith("L") and not include_rscale:
                            lossless = False
                            issues.append(
                                ConversionIssue(
                                    code="leap_month_suffix_stripped",
                                    message=f"Leap month {m!r} stripped of 'L' suffix without RSCALE.",
                                    property_name="byMonth",
                                )
                            )
                            cleaned_months.append(str(m)[:-1])
                        else:
                            cleaned_months.append(str(m))
                    values.append((ical_name, cleaned_months))
                else:
                    values.append((ical_name, [str(v) for v in seq]))

        return ";".join(f"{k}={','.join(v)}" for k, v in values)

    items: list[tuple[str, str]] = []
    if rec.dtstart:
        items.append(("DTSTART", serialize_icalendar_dt(rec.dtstart)))
    if rec.dtend:
        items.append(("DTEND", serialize_icalendar_dt(rec.dtend)))

    for rrule in rec.recurrence_rules:
        items.append(("RRULE", _serialize_rule(rrule)))
    for exrule in rec.excluded_recurrence_rules:
        items.append(("EXRULE", _serialize_rule(exrule)))

    for dt, ov in rec.recurrence_overrides.items():
        if ov.patches:
            lossless = False
            issues.append(
                ConversionIssue(
                    code="override_patches_dropped",
                    message=(
                        f"Override at {dt.isoformat()} has property patches {list(ov.patches.keys())} "
                        "which cannot be represented in RDATE/EXDATE."
                    ),
                    property_name="recurrenceOverrides",
                )
            )
        if ov.excluded:
            items.append(("EXDATE", serialize_icalendar_dt(dt)))
        else:
            items.append(("RDATE", serialize_icalendar_dt(dt)))

    if strict and not lossless:
        msg = "; ".join(issue.message for issue in issues)
        raise exceptions.ConversionError(f"Lossy RFC 8984 -> RFC 5545 conversion: {msg}")

    output = "\n".join(f"{k}:{v}" for k, v in items)
    return ConversionReport(output=output, lossless=lossless, issues=issues)


def jscalendar_to_icalendar(
    obj: JSCalendarRecurrence | RecurrenceRule,
    include_rscale: bool = False,
) -> str:
    """Serialize an RFC 8984 ``JSCalendarRecurrence`` or ``RecurrenceRule`` to RFC 5545 text."""
    return str(
        convert_jscalendar_to_icalendar_with_report(obj, include_rscale=include_rscale).output
    )


_ICAL_TOKEN_RE = re.compile(
    r"(DTSTART|DTEND|RRULE|EXRULE|RDATE|EXDATE)[^:]*:(.*)",
    re.MULTILINE,
)

_BYPARAM_ICAL_TO_ATTR: dict[str, str] = {
    "bysetpos": "by_set_position",
    "bymonth": "by_month",
    "bymonthday": "by_month_day",
    "byyearday": "by_year_day",
    "byweekno": "by_week_no",
    "byhour": "by_hour",
    "byminute": "by_minute",
    "bysecond": "by_second",
}


def convert_icalendar_to_jscalendar_with_report(
    text: str,
    include_dtstart: bool = True,
) -> ConversionReport:
    """
    Parse an RFC 5545 / RFC 2445 string into an RFC 8984 ``JSCalendarRecurrence``
    and return a ``ConversionReport``.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    issues: list[ConversionIssue] = []
    dtstart: datetime.datetime | None = None
    dtend: datetime.datetime | None = None
    rrules: list[RecurrenceRule] = []
    exrules: list[RecurrenceRule] = []
    overrides: dict[datetime.datetime, RecurrenceOverride] = {}

    tokens = _ICAL_TOKEN_RE.findall(text)
    if not tokens and text:
        raise exceptions.DeserializationError("malformed data")

    for label, param_text in tokens:
        param_text = param_text.strip("\r")
        if not param_text:
            raise exceptions.DeserializationError(f"empty property: {label!r}")

        if label in ("RRULE", "EXRULE"):
            params: dict[str, list[str]] = {}
            for item in (p for p in param_text.split(";") if p):
                try:
                    param_name, param_value = [part.strip() for part in item.split("=", 1)]
                except ValueError as exc:
                    raise exceptions.DeserializationError(
                        f"missing parameter value: {item!r}"
                    ) from exc
                params[param_name.upper()] = [part.strip() for part in param_value.split(",")]

            kwargs: dict[str, Any] = {}
            for key, value in params.items():
                if key == "FREQ":
                    freq_lower = value[0].lower()
                    try:
                        Frequency(freq_lower)
                    except ValueError as exc:
                        raise exceptions.DeserializationError(
                            f"bad frequency value: {value[0]!r}"
                        ) from exc
                    kwargs["frequency"] = freq_lower
                elif key == "INTERVAL":
                    try:
                        interval_val = int(value[0])
                        if interval_val < 1:
                            raise ValueError
                        kwargs["interval"] = interval_val
                    except ValueError as exc:
                        raise exceptions.DeserializationError(
                            f"bad interval value: {value[0]!r}"
                        ) from exc
                elif key == "RSCALE":
                    kwargs["rscale"] = value[0].lower()
                elif key == "SKIP":
                    skip_lower = value[0].lower()
                    try:
                        Skip(skip_lower)
                    except ValueError as exc:
                        raise exceptions.DeserializationError(
                            f"bad skip value: {value[0]!r}"
                        ) from exc
                    kwargs["skip"] = skip_lower
                elif key == "WKST":
                    try:
                        nd = NDay.from_icalendar(value[0])
                        kwargs["first_day_of_week"] = nd.day
                    except ValueError as exc:
                        raise exceptions.DeserializationError(
                            f"bad weekday value: {value[0]!r}"
                        ) from exc
                elif key == "COUNT":
                    try:
                        kwargs["count"] = int(value[0])
                    except ValueError as exc:
                        raise exceptions.DeserializationError(
                            f"bad count value: {value[0]!r}"
                        ) from exc
                elif key == "UNTIL":
                    kwargs["until"] = deserialize_icalendar_dt(value[0])
                elif key == "BYDAY":
                    bydays: list[NDay] = []
                    for v in value:
                        try:
                            bydays.append(NDay.from_icalendar(v))
                        except ValueError as exc:
                            raise exceptions.DeserializationError(
                                f"bad weekday value: {v!r}"
                            ) from exc
                    kwargs["by_day"] = bydays
                elif key.lower() in _BYPARAM_ICAL_TO_ATTR:
                    attr_name = _BYPARAM_ICAL_TO_ATTR[key.lower()]
                    if attr_name == "by_month":
                        months: list[str] = []
                        for v in value:
                            v_clean = v[:-1] if v.upper().endswith("L") else v
                            try:
                                int(v_clean)
                            except ValueError as exc:
                                raise exceptions.DeserializationError(
                                    f"bad value: {value!r}"
                                ) from exc
                            months.append(v.upper())
                        kwargs["by_month"] = months
                    else:
                        numbers: list[int] = []
                        for v in value:
                            try:
                                numbers.append(int(v))
                            except ValueError as exc:
                                raise exceptions.DeserializationError(
                                    f"bad value: {value!r}"
                                ) from exc
                        kwargs[attr_name] = numbers
                else:
                    raise exceptions.DeserializationError(f"bad parameter: {key}")

            if "frequency" not in kwargs:
                raise exceptions.DeserializationError("frequency parameter missing from rule")

            rule = RecurrenceRule(**kwargs)
            try:
                rule.validate(strict_rfc8984=False)
            except exceptions.ValidationError as exc:
                raise exceptions.DeserializationError(str(exc.args[0])) from exc

            if label == "RRULE":
                rrules.append(rule)
            else:
                exrules.append(rule)
                issues.append(
                    ConversionIssue(
                        code="exrule_mapped",
                        message="EXRULE mapped to RFC 8984 excludedRecurrenceRules.",
                        property_name="EXRULE",
                    )
                )
        elif label == "DTSTART":
            dtstart = deserialize_icalendar_dt(param_text)
        elif label == "DTEND":
            dtend = deserialize_icalendar_dt(param_text)
        elif label == "RDATE":
            for item in param_text.split(","):
                dt_val = deserialize_icalendar_dt(item)
                overrides[dt_val] = RecurrenceOverride(excluded=False)
        elif label == "EXDATE":
            for item in param_text.split(","):
                dt_val = deserialize_icalendar_dt(item)
                overrides[dt_val] = RecurrenceOverride(excluded=True)

    rec = JSCalendarRecurrence(
        dtstart=dtstart,
        dtend=dtend,
        recurrence_rules=rrules,
        excluded_recurrence_rules=exrules,
        recurrence_overrides=overrides,
        include_dtstart=include_dtstart,
    )
    return ConversionReport(output=rec, lossless=True, issues=issues)


def icalendar_to_jscalendar(text: str, include_dtstart: bool = True) -> JSCalendarRecurrence:
    """Parse an RFC 5545 / RFC 2445 string into an RFC 8984 ``JSCalendarRecurrence``."""
    report = convert_icalendar_to_jscalendar_with_report(text, include_dtstart=include_dtstart)
    return report.output


def deserialize_any(
    value: str | Mapping[str, Any] | JSCalendarRecurrence,
    include_dtstart: bool = True,
) -> JSCalendarRecurrence:
    """
    Auto-detect whether ``value`` is RFC 8984 JSCalendar (dict or JSON string)
    or RFC 5545 / RFC 2445 iCalendar text and return a ``JSCalendarRecurrence``.
    """
    if isinstance(value, JSCalendarRecurrence):
        return value
    if isinstance(value, Mapping):
        return JSCalendarRecurrence.from_jscalendar(value, include_dtstart=include_dtstart)
    if not isinstance(value, str):
        raise TypeError(f"Cannot deserialize recurrence from {type(value).__name__}")

    stripped = value.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise exceptions.DeserializationError(f"Malformed JSON: {exc}") from exc
        if isinstance(parsed, Mapping):
            return JSCalendarRecurrence.from_jscalendar(parsed, include_dtstart=include_dtstart)
        raise exceptions.DeserializationError("JSON recurrence payload must be an object")

    return icalendar_to_jscalendar(value, include_dtstart=include_dtstart)
