"""Legacy relational models for recurrence compatibility."""

from __future__ import annotations

from typing import Any

from django.db import models

import recurrence as recur
from recurrence import choices, managers


class Recurrence(models.Model):
    dtstart: Any = models.DateTimeField(null=True, blank=True)
    dtend: Any = models.DateTimeField(null=True, blank=True)

    objects = managers.RecurrenceManager()

    def to_recurrence_object(self) -> recur.Recurrence:
        return Recurrence.objects.to_recurrence_object(self)

    def to_jscalendar(self) -> dict[str, Any]:
        return self.to_recurrence_object().to_jscalendar()


class Rule(models.Model):
    recurrence: Any = models.ForeignKey(Recurrence, related_name="rules", on_delete=models.CASCADE)
    mode: Any = models.BooleanField(default=True, choices=choices.MODE_CHOICES)
    freq: Any = models.PositiveIntegerField(choices=choices.FREQUENCY_CHOICES)
    interval: Any = models.PositiveIntegerField(default=1)
    wkst: Any = models.PositiveIntegerField(default=recur.Rule.firstweekday, null=True, blank=True)
    count: Any = models.PositiveIntegerField(null=True, blank=True)
    until: Any = models.DateTimeField(null=True, blank=True)

    objects = managers.RuleManager()

    def to_rule_object(self) -> recur.Rule:
        return self.__class__.objects.to_rule_object(self)

    def to_jscalendar(self) -> dict[str, Any]:
        return self.to_rule_object().to_jscalendar()


class Date(models.Model):
    recurrence: Any = models.ForeignKey(Recurrence, related_name="dates", on_delete=models.CASCADE)
    mode: Any = models.BooleanField(default=True, choices=choices.MODE_CHOICES)
    dt: Any = models.DateTimeField()


class Param(models.Model):
    rule: Any = models.ForeignKey(Rule, related_name="params", on_delete=models.CASCADE)
    param: Any = models.CharField(max_length=16)
    value: Any = models.IntegerField()
    index: Any = models.IntegerField(default=0)
