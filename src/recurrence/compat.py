"""Descriptor helper for model fields."""

from __future__ import annotations

from typing import Any


class Creator:
    """
    A descriptor that invokes ``field.to_python(value)`` when an attribute is
    assigned on a model instance.
    """

    def __init__(self, field: Any) -> None:
        self.field = field

    def __get__(self, obj: Any, type: Any = None) -> Any:
        if obj is None:
            return self
        return obj.__dict__[self.field.name]

    def __set__(self, obj: Any, value: Any) -> None:
        obj.__dict__[self.field.name] = self.field.to_python(value)
