"""Test models for both drop-in recurrence and native dj_recurrence fields."""

from __future__ import annotations

from django.db import models

from dj_recurrence.fields import JSCalendarRecurrenceField
from recurrence.fields import RecurrenceField


class EventWithNoNulls(models.Model):
    recurs = RecurrenceField(null=False)


class EventWithNulls(models.Model):
    recurs = RecurrenceField(null=True)


class EventWithJSCalendarStorage(models.Model):
    recurs = RecurrenceField(null=True, storage_format="rfc8984")


class NativeJSCalendarEvent(models.Model):
    title = models.CharField(max_length=120, default="Event")
    recurs = JSCalendarRecurrenceField(null=True, blank=True)
