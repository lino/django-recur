"""Re-export migrate_recurrences command under the ``recurrence`` app."""

from __future__ import annotations

from django_recur.management.commands.migrate_recurrences import Command

__all__ = ["Command"]
