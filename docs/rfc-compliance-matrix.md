# RFC 8984 & RFC 5545 Feature & Auto-Mapping Matrix

A central design requirement of `django-recurrence-jscalendar` is transparent, auditable interoperability between:

- **RFC 8984 (JSCalendar: A JSON Representation of Calendar Data)** — specifically §4.3 (*Recurrence Properties*: `recurrenceRules`, `excludedRecurrenceRules`, `recurrenceOverrides`, `excluded`) and the `RecurrenceRule` / `NDay` data types.
- **RFC 5545 (Internet Calendaring and Scheduling Core Object Specification — iCalendar)** — along with legacy **RFC 2445** (`EXRULE`) as used by `django-recurrence` and **RFC 7529** (`RSCALE` / `SKIP` extensions).

This page documents every recurrence property, its implementation status in `django-recurrence-jscalendar`, and whether it can be **automatically mapped** between RFC 8984 and RFC 5545.

---

## Auto-Mapping Classifications

Both the documentation below and the runtime `dj_recurrence.rfc5545.FEATURE_MATRIX` classify every feature mapping using four levels:

| Classification | Meaning | Behavior in `strict=False` (Default) | Behavior in `strict=True` |
| --- | --- | --- | --- |
| **`lossless`** | 1:1 semantic and structural equivalence between RFC 8984 and RFC 5545. | Automatically mapped without warnings. | Automatically mapped without errors. |
| **`conditional`** | Lossless for standard values; requires an extension (e.g., RFC 7529 `RSCALE`/`SKIP` or RFC 2445 `EXRULE`) or value normalization for non-default inputs. | Automatically mapped; records an informational/warning `ConversionIssue` when non-standard values are used. | Raises `ConversionError` if a lossy fallback is triggered. |
| **`lossy`** | One specification is strictly richer than the other (e.g., RFC 8984 `recurrenceOverrides` containing per-occurrence property patches like `{"title": "Moved"}` mapped to flat `RDATE`). | Automatically maps the recurrence timestamp (`RDATE`) and records a `lossy` `ConversionIssue` in `ConversionReport`. | Raises `ConversionError`. |
| **`unsupported`** | Not part of the recurrence specification. | Recorded in `ConversionReport`. | Raises `ConversionError`. |

---

## Master Feature & Auto-Mapping Matrix

### 1. Top-Level Recurrence Container Properties

| Feature / Concept | RFC 8984 (JSCalendar §4.3) | RFC 5545 / RFC 2445 (iCalendar) | Implemented | Auto-Map: `8984 → 5545` | Auto-Map: `5545 → 8984` | Notes & Edge Cases |
| --- | --- | --- | --- | --- | --- | --- |
| **Start Date/Time** | `start` (`LocalDateTime` / `UTCDateTime`) | `DTSTART` (`DATE-TIME` / `DATE`) | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Naive datetimes map to RFC 8984 `LocalDateTime`; UTC/aware datetimes normalize to `Z` in `DTSTART` and `start`. |
| **End / Bound Date/Time** | `dtend` (extension for `django-recurrence` compatibility) | `DTEND` (`DATE-TIME` / `DATE`) | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Preserved across both formats to maintain 100% compatibility with `django-recurrence.Recurrence(dtend=...)`. |
| **Inclusion Rules** | `recurrenceRules: RecurrenceRule[]` | Multiple `RRULE:` lines | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Preserves rule ordering across multiple rules. |
| **Exclusion Rules** | `excludedRecurrenceRules: RecurrenceRule[]` | `EXRULE:` lines (RFC 2445; deprecated in RFC 5545) | Yes | **Yes (`conditional`)** | **Yes (`lossless`)** | RFC 8984 natively reinstated `excludedRecurrenceRules`. Mapping to iCalendar emits `EXRULE:` lines (compatible with `django-recurrence` and `python-dateutil`) and logs a `conditional` note in `ConversionReport` since RFC 5545 deprecated `EXRULE` from RFC 2445. |
| **Additional Inclusion Dates** | `recurrenceOverrides: { "<LocalDateTime>": {} }` | `RDATE:` lines | Yes | **Yes (`lossless` for empty patch, `lossy` for property patches)** | **Yes (`lossless`)** | An empty override `{}` in RFC 8984 maps losslessly to `RDATE` in RFC 5545 and back. |
| **Excluded Dates** | `recurrenceOverrides: { "<LocalDateTime>": { "excluded": true } }` | `EXDATE:` lines | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Maps `{"excluded": true}` in `recurrenceOverrides` directly to `EXDATE` and vice versa. |
| **Per-Occurrence Property Patches** | `recurrenceOverrides: { "<LocalDateTime>": { "title": "...", "duration": "..." } }` | Separate VEVENT component with `RECURRENCE-ID` | Yes (in RFC 8984 model) | **Partial (`lossy` in single-rule string)** | N/A | A standalone `django-recurrence` rule string does not contain multiple `VEVENT` components; therefore, non-empty property patches degrade to `RDATE` with a `lossy` issue recorded in `ConversionReport`. |

---

### 2. `RecurrenceRule` / `RRULE` Parts

| Rule Part | RFC 8984 (`RecurrenceRule`) | RFC 5545 (`RRULE` / `EXRULE`) | Implemented | Auto-Map: `8984 → 5545` | Auto-Map: `5545 → 8984` | Notes & Edge Cases |
| --- | --- | --- | --- | --- | --- | --- |
| **Object Type** | `@type: "RecurrenceRule"` | Implicit in `RRULE:` / `EXRULE:` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Validated on JSON deserialization; defaults to `"RecurrenceRule"`. |
| **Frequency** | `frequency`: `"yearly"` \| `"monthly"` \| `"weekly"` \| `"daily"` \| `"hourly"` \| `"minutely"` \| `"secondly"` | `FREQ=YEARLY\|MONTHLY\|WEEKLY\|DAILY\|HOURLY\|MINUTELY\|SECONDLY` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Case-insensitive mapping between lowercase RFC 8984 strings, uppercase RFC 5545 tokens, and `recurrence` integer constants (`0..6`). |
| **Interval** | `interval` (`UnsignedInt >= 1`, default `1`) | `INTERVAL=<int>` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Per RFC 8984 §4.3.3, default value `1` is omitted in compact JSON serialization unless `include_defaults=True`. |
| **Calendar Scale** | `rscale` (`String`, default `"gregorian"`) | `RSCALE=<scale>` (RFC 7529 extension; not in base RFC 5545) | Yes | **Yes (`conditional`)** | **Yes (`lossless`)** | Default `"gregorian"` is lossless. Non-Gregorian scales emit `RSCALE=` (RFC 7529) and record a `conditional` notice in `ConversionReport`. |
| **Invalid Date Skip Behavior** | `skip`: `"omit"` (default) \| `"backward"` \| `"forward"` | `SKIP=OMIT\|BACKWARD\|FORWARD` (RFC 7529 extension; base RFC 5545 only supports omit) | Yes | **Yes (`conditional`)** | **Yes (`lossless`)** | `dj_recurrence` natively expands `skip="backward"` (e.g., Feb 29 → Feb 28 in non-leap years) and `skip="forward"` (Feb 29 → Mar 1). Emits `SKIP=` in RFC 5545 strings with a `conditional` notice. |
| **First Day of Week** | `firstDayOfWeek`: `"mo"` \| `"tu"` \| `"we"` \| `"th"` \| `"fr"` \| `"sa"` \| `"su"` (default `"mo"`) | `WKST=MO\|TU\|WE\|TH\|FR\|SA\|SU` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Bidirectional 1:1 mapping with `recurrence.Weekday` and integer weekday indices (`0..6`). |
| **By Day (`NDay`)** | `byDay: NDay[]` (`{"@type": "NDay", "day": "mo", "nthOfPeriod": 1}`) | `BYDAY=1MO,-1FR,WE` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Full bidirectional conversion between RFC 8984 `NDay` objects (`day` + optional `nthOfPeriod`), RFC 5545 `[±n]WKDAY` tokens, and `recurrence.Weekday(number, index)`. |
| **By Month** | `byMonth: String[]` (`"1".."12"`, or `"5L"` for leap months) | `BYMONTH=1,2,...,12` (`5L` requires RFC 7529) | Yes | **Yes (`conditional`)** | **Yes (`lossless`)** | Standard months `"1"`–`"12"` map 1:1 to `int` `1`–`12` (`lossless`). Leap-month strings ending in `"L"` (e.g. `"5L"`) are flagged as `conditional` / `lossy` when converting to legacy `recurrence.Rule` integer lists. |
| **By Month Day** | `byMonthDay: Int[]` (`-31..-1`, `1..31`) | `BYMONTHDAY=-31..-1,1..31` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Validated to exclude `0` or out-of-range integers per RFC 8984 §4.3.3 and RFC 5545 §3.3.10. |
| **By Year Day** | `byYearDay: Int[]` (`-366..-1`, `1..366`) | `BYYEARDAY=-366..-1,1..366` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Validated to exclude `0` or values outside `±366`. |
| **By Week Number** | `byWeekNo: Int[]` (`-53..-1`, `1..53`) | `BYWEEKNO=-53..-1,1..53` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Validated to exclude `0` or values outside `±53`. |
| **By Hour** | `byHour: UnsignedInt[]` (`0..23`) | `BYHOUR=0..23` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Validated in `0..23`. |
| **By Minute** | `byMinute: UnsignedInt[]` (`0..59`) | `BYMINUTE=0..59` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Validated in `0..59`. |
| **By Second** | `bySecond: UnsignedInt[]` (`0..60`) | `BYSECOND=0..60` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Includes leap second `60` per both RFCs. |
| **By Set Position** | `bySetPosition: Int[]` (`-366..-1`, `1..366`) | `BYSETPOS=-366..-1,1..366` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Filters candidate occurrences within each period before `count` / `until`. |
| **Count Limit** | `count: UnsignedInt` (`>= 1`) | `COUNT=<int>` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Mutually exclusive with `until` / `UNTIL` in both RFC 8984 and RFC 5545. Enforced by validation. |
| **Until Limit** | `until: LocalDateTime \| UTCDateTime` | `UNTIL=<DATE-TIME \| DATE>` | Yes | **Yes (`lossless`)** | **Yes (`lossless`)** | Mutually exclusive with `count` / `COUNT`. |

---

## Programmatic Access to the Matrix & Conversion Reports

You can inspect the feature matrix or audit any conversion at runtime using `dj_recurrence.rfc5545`:

```python
from dj_recurrence.rfc5545 import (
    FEATURE_MATRIX,
    convert_jscalendar_to_icalendar_with_report,
    convert_icalendar_to_jscalendar_with_report,
)
from dj_recurrence.rfc8984 import Frequency, JSCalendarRecurrence, RecurrenceRule, Skip

# 1. Inspect the programmatic feature matrix
for entry in FEATURE_MATRIX:
    print(
        f"{entry['feature']}: "
        f"8984->5545={entry['auto_map_8984_to_5545']} | "
        f"5545->8984={entry['auto_map_5545_to_8984']}"
    )

# 2. Audit an RFC 8984 -> RFC 5545 conversion
rec = JSCalendarRecurrence(
    recurrence_rules=[
        RecurrenceRule(
            frequency=Frequency.YEARLY,
            by_month=["2"],
            by_month_day=[29],
            skip=Skip.BACKWARD,
        )
    ]
)
ical_str, report = convert_jscalendar_to_icalendar_with_report(rec)
print(ical_str)
# RRULE:FREQ=YEARLY;SKIP=BACKWARD;BYMONTH=2;BYMONTHDAY=29
print(report.issues)
# [ConversionIssue(feature='skip', direction='8984->5545', status='conditional', ...)]
```
