# `dj_recurrence` API Reference

The `dj_recurrence` package provides the native **RFC 8984 (JSCalendar)** data model, **RFC 5545 (iCalendar)** conversion and audit tools, `JSCalendarRecurrenceField`, and `<dj-recurrence-widget>`.

---

## RFC 8984 Data Model (`dj_recurrence.rfc8984`)

### `Frequency` (`StrEnum`)

Enumeration of RFC 8984 §4.3.3 recurrence frequencies:

- `Frequency.YEARLY = "yearly"`
- `Frequency.MONTHLY = "monthly"`
- `Frequency.WEEKLY = "weekly"`
- `Frequency.DAILY = "daily"`
- `Frequency.HOURLY = "hourly"`
- `Frequency.MINUTELY = "minutely"`
- `Frequency.SECONDLY = "secondly"`

Helper methods:

- `Frequency.from_any(value)`: Parse from `Frequency`, RFC 8984 lowercase string (`"weekly"`), RFC 5545 uppercase string (`"WEEKLY"`), or legacy `recurrence` integer (`0..6`).
- `freq.to_legacy_int()`: Convert to legacy `recurrence` integer (`0..6`).
- `freq.to_rfc5545()`: Convert to uppercase RFC 5545 frequency string.

---

### `DayOfWeek` (`StrEnum`)

Enumeration of RFC 8984 §4.3.3 weekday identifiers:

- `DayOfWeek.MONDAY = "mo"`
- `DayOfWeek.TUESDAY = "tu"`
- `DayOfWeek.WEDNESDAY = "we"`
- `DayOfWeek.THURSDAY = "th"`
- `DayOfWeek.FRIDAY = "fr"`
- `DayOfWeek.SATURDAY = "sa"`
- `DayOfWeek.SUNDAY = "su"`

---

### `Skip` (`StrEnum`)

Enumeration of RFC 8984 §4.3.3 invalid-date skip strategies:

- `Skip.OMIT = "omit"` (default)
- `Skip.BACKWARD = "backward"`
- `Skip.FORWARD = "forward"`

---

### `NDay`

Represents an RFC 8984 `NDay` object (`{"@type": "NDay", "day": "mo", "nthOfPeriod": 1}`).

- `day: DayOfWeek`
- `nth_of_period: int | None = None` (`-53..53`, non-zero)
- `to_jscalendar(include_defaults: bool = False) -> dict[str, Any]`
- `from_jscalendar(cls, data: Mapping[str, Any] | str) -> NDay`
- `to_rfc5545() -> str` (e.g., `"1MO"`, `"-1FR"`, `"WE"`)
- `from_rfc5545(cls, token: str) -> NDay`

---

### `RecurrenceRule`

Represents an RFC 8984 `RecurrenceRule` object (§4.3.3).

- `frequency: Frequency`
- `interval: int = 1`
- `rscale: str = "gregorian"`
- `skip: Skip = Skip.OMIT`
- `first_day_of_week: DayOfWeek = DayOfWeek.MONDAY`
- `by_day: list[NDay] = []`
- `by_month_day: list[int] = []`
- `by_month: list[str] = []`
- `by_year_day: list[int] = []`
- `by_week_no: list[int] = []`
- `by_hour: list[int] = []`
- `by_minute: list[int] = []`
- `by_second: list[int] = []`
- `by_set_position: list[int] = []`
- `count: int | None = None`
- `until: datetime | None = None`
- `to_jscalendar(include_defaults: bool = False) -> dict[str, Any]`
- `from_jscalendar(cls, data: Mapping[str, Any]) -> RecurrenceRule`
- `to_dateutil_rrule(dtstart: datetime | None = None, cache: bool = False)`
- `to_text(short: bool = False) -> str`

---

### `RecurrenceOverride`

Represents a single entry in RFC 8984 `recurrenceOverrides`:

- `excluded: bool = False`
- `patches: dict[str, Any] = {}`
- `to_jscalendar() -> dict[str, Any]`
- `from_jscalendar(cls, data: Mapping[str, Any]) -> RecurrenceOverride`

---

### `JSCalendarRecurrence`

Container for RFC 8984 §4.3 recurrence properties:

- `start: datetime | None = None`
- `dtend: datetime | None = None`
- `recurrence_rules: list[RecurrenceRule] = []`
- `excluded_recurrence_rules: list[RecurrenceRule] = []`
- `recurrence_overrides: dict[datetime, RecurrenceOverride] = {}`
- `include_dtstart: bool = True`
- `occurrences(dtstart=None, dtend=None, cache=False) -> Iterator[datetime]`
- `between(after, before, inc=False, dtstart=None, dtend=None, cache=False) -> list[datetime]`
- `after(dt, inc=False, dtstart=None, dtend=None, cache=False) -> datetime | None`
- `before(dt, inc=False, dtstart=None, dtend=None, cache=False) -> datetime | None`
- `count(dtstart=None, dtend=None, cache=False) -> int`
- `to_jscalendar(include_defaults: bool = False) -> dict[str, Any]`
- `from_jscalendar(cls, data: Mapping[str, Any]) -> JSCalendarRecurrence`
- `to_json(include_defaults: bool = False) -> str`
- `from_json(cls, raw: str) -> JSCalendarRecurrence`
- `to_icalendar() -> str`
- `from_icalendar(cls, text: str) -> JSCalendarRecurrence`

---

## RFC 5545 Conversion & Audit (`dj_recurrence.rfc5545`)

- `FEATURE_MATRIX`: List of dictionaries describing every RFC 8984 / RFC 5545 feature and its auto-mapping status.
- `ConversionIssue`: Dataclass recording a `feature`, `direction`, `status` (`"lossless" | "conditional" | "lossy" | "unsupported"`), and `message`.
- `ConversionReport`: Dataclass aggregating `issues` with `is_lossless` and `has_lossy_changes` properties.
- `convert_jscalendar_to_icalendar_with_report(recurrence, *, strict=False) -> tuple[str, ConversionReport]`
- `convert_icalendar_to_jscalendar_with_report(text, *, default_include_dtstart=True, strict=False) -> tuple[JSCalendarRecurrence, ConversionReport]`
- `deserialize_any(value, *, default_include_dtstart=True) -> JSCalendarRecurrence`

---

## Django Model & Form Fields (`dj_recurrence.fields`, `dj_recurrence.forms`, `dj_recurrence.widgets`)

- `JSCalendarRecurrenceField`: Subclass of `django.db.models.JSONField` that stores RFC 8984 JSCalendar JSON in the database and returns `JSCalendarRecurrence` objects in Python.
- `JSCalendarRecurrenceFormField`: Django form field that accepts RFC 8984 JSON, RFC 5545 text, or `JSCalendarRecurrence` objects and returns a validated `JSCalendarRecurrence`.
- `RecurrenceWidget` / `JSCalendarRecurrenceWidget`: Renders `<dj-recurrence-widget>` around a synced `<textarea>`.
