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

from django_recur import exceptions
from django_recur.rfc8984 import (
    Frequency,
    JSCalendarRecurrence,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    Skip,
    calendar_time_zone,
    deserialize_tz_enabled,
    format_local_datetime,
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
        rfc8984_property="start (LocalDateTime) and timeZone",
        rfc5545_property="DTSTART",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="conditional",
        notes="Supports IANA TZID, UTC and floating times. DATE values are promoted to midnight.",
    ),
    FeatureMatrixEntry(
        feature_id="end_dtend",
        rfc8984_property="dtend (compatibility extension)",
        rfc5545_property="DTEND",
        rfc8984_implemented=True,
        rfc5545_implemented=True,
        auto_mapping="conditional",
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


def deserialize_icalendar_dt(
    text: str, *, time_zone: str | None = None, legacy: bool = True
) -> datetime.datetime:
    """Parse an RFC 5545 / RFC 2445 ``DATE-TIME`` or ``DATE`` string."""
    cleaned = text.strip().upper()
    if not re.fullmatch(r"[0-9]{8}(?:T[0-9]{6}Z?)?", cleaned):
        raise exceptions.DeserializationError(f"malformed date-time: {text!r}")
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

    if cleaned.endswith("Z"):
        tzinfo: datetime.tzinfo | None = tz.UTC
    elif time_zone is not None:
        tzinfo = calendar_time_zone(time_zone)
    else:
        tzinfo = get_current_timezone() if legacy else None
    try:
        dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=tzinfo)
    except ValueError as exc:
        raise exceptions.DeserializationError(f"malformed date-time: {text!r}") from exc

    if deserialize_tz_enabled():
        return dt
    if not legacy or time_zone is not None:
        return dt.replace(tzinfo=None)

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

    zone_name = rec._serialization_time_zone()
    zone = calendar_time_zone(zone_name) if zone_name is not None else None

    def format_date(property_name: str, value: datetime.datetime) -> tuple[str, str]:
        nonlocal lossless
        if value.microsecond:
            lossless = False
            issues.append(
                ConversionIssue(
                    code="fractional_seconds_dropped",
                    message=f"{property_name} cannot represent fractional seconds.",
                    property_name=property_name,
                )
            )
        wall_time = value if value.tzinfo is not None else value.replace(tzinfo=zone)
        if property_name == "UNTIL" and zone is not None:
            return property_name, serialize_icalendar_dt(wall_time)
        if zone_name == "UTC":
            return property_name, serialize_icalendar_dt(wall_time)
        if zone_name is not None:
            property_name = f"{property_name};TZID={zone_name}"
        local = format_local_datetime(wall_time.replace(microsecond=0), zone)
        return property_name, local.replace("-", "").replace(":", "")

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

        if include_rscale and (rule.rscale != "gregorian" or rule.skip != Skip.OMIT.value):
            values.append(("RSCALE", [rule.rscale.upper()]))
        elif rule.rscale != "gregorian":
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
            values.append(("UNTIL", [format_date("UNTIL", rule.until)[1]]))

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
        items.append(format_date("DTSTART", rec.dtstart))
    if rec.dtend:
        items.append(format_date("DTEND", rec.dtend))

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
            items.append(format_date("EXDATE", dt))
        else:
            items.append(format_date("RDATE", dt))

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
    r"^(DTSTART|DTEND|RRULE|EXRULE|RDATE|EXDATE)((?:;[^:\r\n]+)?):([^\r\n]*)",
    re.MULTILINE | re.IGNORECASE,
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
    *,
    legacy: bool = False,
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

    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    tokens = _ICAL_TOKEN_RE.findall(unfolded)
    if not tokens and text:
        raise exceptions.DeserializationError("malformed data")

    def tzid(parameters: str) -> str | None:
        match = re.search(r'(?:^|;)TZID=(?:"([^"]+)"|([^;]+))', parameters, re.IGNORECASE)
        return (match[1] or match[2]) if match else None

    time_zone = None
    if not legacy:
        date_properties = ("DTSTART", "DTEND", "RDATE", "EXDATE")
        dated = [entry for entry in tokens if entry[0].upper() in date_properties]
        if dated:
            _, parameters, value = next(
                (entry for entry in dated if entry[0].upper() == "DTSTART"), dated[0]
            )
            time_zone = tzid(parameters)
            if time_zone is None and value.split(",")[0].strip().upper().endswith("Z"):
                time_zone = "UTC"
        elif any(
            re.search(r"(?:^|;)UNTIL=[0-9]{8}T[0-9]{6}Z(?:;|$)", value, re.IGNORECASE)
            for _, _, value in tokens
        ):
            time_zone = "UTC"
    zone = calendar_time_zone(time_zone) if time_zone is not None else None
    lossless = True

    def parse_date(property_name: str, value: str, parameters: str = "") -> datetime.datetime:
        nonlocal lossless
        source_name = tzid(parameters)
        utc = value.strip().upper().endswith("Z")
        source = tz.UTC if utc else calendar_time_zone(source_name) if source_name else None
        result = deserialize_icalendar_dt(value, time_zone=source_name, legacy=legacy)
        if legacy:
            return result
        if len(value.strip()) == 8:
            lossless = False
            issues.append(
                ConversionIssue(
                    code="date_value_promoted",
                    message=f"{property_name} DATE values were converted to midnight date-times.",
                    property_name=property_name,
                )
            )
        if (source is None) != (zone is None):
            lossless = False
            issues.append(
                ConversionIssue(
                    code="mixed_time_modes",
                    message=f"{property_name} mixes floating and timezone-bound date-times.",
                    property_name=property_name,
                )
            )
        if source is not None and zone is not None:
            adjusted = result.replace(tzinfo=source).astimezone(zone)
            if adjusted.fold:
                lossless = False
                issues.append(
                    ConversionIssue(
                        code="ambiguous_local_time",
                        message=f"{value} maps to the later instance of a repeated local time.",
                        property_name=property_name,
                    )
                )
            return adjusted if deserialize_tz_enabled() else adjusted.replace(tzinfo=None)
        return result

    for label, parameters, param_text in tokens:
        label = label.upper()
        param_text = param_text.strip()
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
                    kwargs["until"] = parse_date("UNTIL", value[0])
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
            dtstart = parse_date(label, param_text, parameters)
        elif label == "DTEND":
            dtend = parse_date(label, param_text, parameters)
        elif label == "RDATE":
            for item in param_text.split(","):
                dt_val = parse_date(label, item, parameters)
                overrides.setdefault(dt_val, RecurrenceOverride(excluded=False))
        elif label == "EXDATE":
            for item in param_text.split(","):
                dt_val = parse_date(label, item, parameters)
                overrides[dt_val] = RecurrenceOverride(excluded=True)

    rec = JSCalendarRecurrence(
        dtstart=dtstart,
        dtend=dtend,
        recurrence_rules=rrules,
        excluded_recurrence_rules=exrules,
        recurrence_overrides=overrides,
        time_zone=time_zone,
        include_dtstart=include_dtstart,
    )
    return ConversionReport(output=rec, lossless=lossless, issues=issues)


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
