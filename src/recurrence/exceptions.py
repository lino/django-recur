"""Exceptions for the recurrence compatibility layer (re-exported from dj_recurrence)."""

from __future__ import annotations

from dj_recurrence.exceptions import (
    ConversionError,
    DeserializationError,
    RecurrenceError,
    SerializationError,
    UnsupportedFeatureError,
    ValidationError,
)

__all__ = [
    "ConversionError",
    "DeserializationError",
    "RecurrenceError",
    "SerializationError",
    "UnsupportedFeatureError",
    "ValidationError",
]
