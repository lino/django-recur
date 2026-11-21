# `recurrence` Drop-In Compatibility API Reference

The `recurrence` package provides 100% drop-in compatibility with [`jazzband/django-recurrence`](https://github.com/jazzband/django-recurrence) while delegating occurrence evaluation and validation to the RFC 8984 (`django_recur`) engine.

---

## Core Classes (`recurrence.base`)

### `recurrence.Weekday`

Represents a weekday with an optional relative occurrence index:

- `Weekday(number: int, index: int | None = None)`
- `number`: `0` (Monday) through `6` (Sunday)
- `index`: Optional non-zero integer (`1`, `2`, `-1`, etc.)
- `weekday(index: int) -> Weekday`: Return a copy with `index` set (e.g. `recurrence.MO(2)` or `recurrence.FR(-1)`).
- `to_nday() -> django_recur.NDay`: Convert to an RFC 8984 `NDay` instance.
- `from_nday(cls, nday: NDay) -> Weekday`: Construct from an RFC 8984 `NDay` instance.

Predefined constants:

- `MONDAY`, `TUESDAY`, `WEDNESDAY`, `THURSDAY`, `FRIDAY`, `SATURDAY`, `SUNDAY`
- `MO`, `TU`, `WE`, `TH`, `FR`, `SA`, `SU`

---

### `recurrence.Rule`

Represents an inclusion or exclusion rule (`RRULE` or `EXRULE`) backed by `django_recur.RecurrenceRule`:

```python
Rule(
    freq,
    interval=1,
    wkst=None,
    count=None,
    until=None,
    bysetpos=None,
    bymonth=None,
    bymonthday=None,
    byyearday=None,
    byweekno=None,
    byday=None,
    byhour=None,
    byminute=None,
    bysecond=None,
    rscale="gregorian",
    skip="omit",
)
```

Methods:

- `to_text(short: bool = False) -> str`
- `to_dateutil_rrule(dtstart=None, dtend=None, cache=False)`
- `to_jscalendar_rule() -> django_recur.RecurrenceRule`
- `from_jscalendar_rule(cls, rule: django_recur.RecurrenceRule) -> Rule`

---

### `recurrence.Recurrence`

Represents a complete recurrence schedule compatible with `django-recurrence`:

```python
Recurrence(
    dtstart=None,
    dtend=None,
    rrules=(),
    exrules=(),
    rdates=(),
    exdates=(),
    include_dtstart=True,
)
```

Methods:

- `occurrences(dtstart=None, dtend=None, cache=False) -> Iterator[datetime]`
- `between(after, before, inc=False, dtstart=None, dtend=None, cache=False) -> list[datetime]`
- `after(dt, inc=False, dtstart=None, dtend=None, cache=False) -> datetime | None`
- `before(dt, inc=False, dtstart=None, dtend=None, cache=False) -> datetime | None`
- `count(dtstart=None, dtend=None, cache=False) -> int`
- `to_dateutil_rruleset(dtstart=None, dtend=None, cache=False)`
- `to_jscalendar_obj() -> django_recur.JSCalendarRecurrence`
- `from_jscalendar_obj(cls, jscal: django_recur.JSCalendarRecurrence) -> Recurrence`
- `to_jscalendar_dict(include_defaults: bool = False) -> dict[str, Any]`
- `to_jscalendar_json(include_defaults: bool = False) -> str`

---

## Serialization Functions (`recurrence.base`)

- `serialize(rule_or_recurrence, format: str | None = None) -> str`: Serializes a `Rule`, `Recurrence`, or `JSCalendarRecurrence` to RFC 5545 text (`format="rfc5545"`, default) or RFC 8984 JSON (`format="rfc8984"`).
- `deserialize(text, include_dtstart: bool = True) -> Recurrence`: Automatically detects and parses either RFC 5545 / RFC 2445 text or RFC 8984 JSCalendar JSON into a `Recurrence` object.
- `to_weekday(token) -> Weekday`: Converts a `Weekday`, `NDay`, integer (`0..6`), or weekday string (`"MO"`, `"1MO"`, `"-2FR"`, `"mo"`) into a `Weekday` instance.
- `from_dateutil_rrule(rrule) -> Rule`
- `from_dateutil_rruleset(rruleset) -> Recurrence`

---

## Django Model Field & Forms (`recurrence.fields`, `recurrence.forms`, `recurrence.models`)

- `recurrence.fields.RecurrenceField(include_dtstart=True, storage_format=None, **kwargs)`: Stores recurrence rules in a database text column while transparently reading both RFC 5545 strings and RFC 8984 JSON.
- `recurrence.forms.RecurrenceField`: Form field validating and normalizing recurrence inputs.
- `recurrence.forms.RecurrenceWidget`: Progressive-enhancement Web Component widget (`<django-recur-widget>`).
- `recurrence.models.Recurrence`, `recurrence.models.Rule`, `recurrence.models.Date`, `recurrence.models.Param`: Relational models and managers (`RecurrenceManager`, `RuleManager`) preserved for legacy relational schemas.
