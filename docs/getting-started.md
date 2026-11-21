# Quickstart

`django-recur` supports two ways of working with recurring events in Django:

1. **Modern Native RFC 8984 (JSCalendar) Mode** via `django_recur`
2. **Drop-In `django-recurrence` Compatibility Mode** via `recurrence`

---

## 1. Modern Native RFC 8984 Mode (`django_recur`)

Use `JSCalendarRecurrenceField` on your Django models to store recurrences as native JSON (`JSONField`) conforming to RFC 8984 §4.3:

```python
from datetime import datetime
from django.db import models
from django_recur import (
    DayOfWeek,
    Frequency,
    JSCalendarRecurrence,
    JSCalendarRecurrenceField,
    NDay,
    RecurrenceOverride,
    RecurrenceRule,
    Skip,
)


class CalendarEvent(models.Model):
    title = models.CharField(max_length=200)
    schedule = JSCalendarRecurrenceField()
```

Creating and expanding an RFC 8984 schedule:

```python
schedule = JSCalendarRecurrence(
    start=datetime(2026, 1, 5, 9, 0),
    recurrence_rules=[
        RecurrenceRule(
            frequency=Frequency.WEEKLY,
            interval=2,
            by_day=[NDay(day=DayOfWeek.MONDAY), NDay(day=DayOfWeek.WEDNESDAY)],
            count=6,
        )
    ],
    recurrence_overrides={
        datetime(2026, 1, 19, 9, 0): RecurrenceOverride(excluded=True),
        datetime(2026, 1, 22, 9, 0): RecurrenceOverride(title="Rescheduled Session"),
    },
)

event = CalendarEvent.objects.create(title="Architecture Sync", schedule=schedule)

# Expand occurrences in a date range:
occurrences = event.schedule.between(
    datetime(2026, 1, 1),
    datetime(2026, 3, 1),
    inc=True,
)
```

### Converting Between RFC 8984 and RFC 5545

Every `JSCalendarRecurrence` can serialize to and parse from RFC 5545 iCalendar strings:

```python
# Export RFC 5545 iCalendar text
ical_text = schedule.to_icalendar()

# Parse RFC 5545 iCalendar text back into RFC 8984 JSCalendarRecurrence
parsed = JSCalendarRecurrence.from_icalendar(ical_text)

# Inspect a detailed conversion report (lossless / conditional / lossy warnings)
ical_text, report = schedule.to_icalendar_with_report()
assert report.lossless
```

---

## 2. Drop-In `django-recurrence` Compatibility Mode (`recurrence`)

Existing code written for `jazzband/django-recurrence` runs without changing a single import:

```python
from datetime import datetime
from django.db import models
import recurrence
from recurrence.fields import RecurrenceField


class Course(models.Model):
    title = models.CharField(max_length=200)
    recurrences = RecurrenceField()
```

Working with `recurrence.Recurrence` and `recurrence.Rule`:

```python
rule = recurrence.Rule(
    recurrence.WEEKLY,
    interval=1,
    byday=[recurrence.MO, recurrence.FR],
)
pattern = recurrence.Recurrence(
    dtstart=datetime(2026, 1, 1),
    dtend=datetime(2026, 1, 31),
    rrules=[rule],
    exdates=[datetime(2026, 1, 9)],
)

# Expand occurrences
dates = pattern.occurrences()

# Convert directly between legacy Recurrence and RFC 8984 JSCalendarRecurrence
jscal = pattern.to_jscalendar_obj()
roundtripped = recurrence.Recurrence.from_jscalendar_obj(jscal)
```
