"""Exceptions for dj_recurrence and recurrence compatibility."""

from __future__ import annotations

from django.core.exceptions import ValidationError


class RecurrenceError(ValidationError):
    """Base exception for all recurrence-related errors."""


class SerializationError(RecurrenceError):
    """Raised when a recurrence rule or set cannot be serialized."""


class DeserializationError(RecurrenceError):
    """Raised when an RFC 8984 or RFC 5545 payload cannot be deserialized."""


class ConversionError(RecurrenceError):
    """Raised when strict conversion between RFC 8984 and RFC 5545 fails."""


class UnsupportedFeatureError(RecurrenceError):
    """Raised when a valid specification feature is not supported for expansion."""


__all__ = [
    "ConversionError",
    "DeserializationError",
    "RecurrenceError",
    "SerializationError",
    "UnsupportedFeatureError",
    "ValidationError",
]
