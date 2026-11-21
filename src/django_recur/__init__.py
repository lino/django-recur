"""
django_recur: Modern RFC 8984 (JSCalendar) & RFC 5545 recurrence engine for Django.
"""

from __future__ import annotations

from django_recur.exceptions import (
    ConversionError,
    DeserializationError,
    RecurrenceError,
    SerializationError,
    UnsupportedFeatureError,
    ValidationError,
)
from django_recur.rfc5545 import (
    FEATURE_MATRIX,
    ConversionIssue,
    ConversionReport,
    FeatureMatrixEntry,
    convert_icalendar_to_jscalendar_with_report,
    convert_jscalendar_to_icalendar_with_report,
    deserialize_any,
    icalendar_to_jscalendar,
    jscalendar_to_icalendar,
)
from django_recur.rfc8984 import (
    DayOfWeek,
    Frequency,
    JSCalendarRecurrence,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    Skip,
    format_jscalendar_datetime,
    normalize_offset_awareness,
    parse_jscalendar_datetime,
    to_utc,
)
from django_recur.text import rule_to_text

__version__ = "2.0.0"

__all__ = [
    "FEATURE_MATRIX",
    "ConversionError",
    "ConversionIssue",
    "ConversionReport",
    "DayOfWeek",
    "DeserializationError",
    "FeatureMatrixEntry",
    "Frequency",
    "JSCalendarRecurrence",
    "NDay",
    "RecurrenceError",
    "RecurrenceOverride",
    "RecurrenceRule",
    "SerializationError",
    "Skip",
    "UnsupportedFeatureError",
    "ValidationError",
    "__version__",
    "convert_icalendar_to_jscalendar_with_report",
    "convert_jscalendar_to_icalendar_with_report",
    "deserialize_any",
    "format_jscalendar_datetime",
    "icalendar_to_jscalendar",
    "jscalendar_to_icalendar",
    "normalize_offset_awareness",
    "parse_jscalendar_datetime",
    "rule_to_text",
    "to_utc",
]
