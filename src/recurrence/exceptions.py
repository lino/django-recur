"""Exceptions for the recurrence compatibility layer (re-exported from django_recur)."""

from __future__ import annotations

from django_recur.exceptions import (
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
