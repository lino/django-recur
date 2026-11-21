# TypeScript Web Component Widget (`<django-recur-widget>`)

`django-recur` replaces the legacy prototype-based JavaScript widget from `django-recurrence` with a zero-dependency **Custom Element (`<django-recur-widget>`)** authored in strict TypeScript and bundled with Vite.

---

## Architecture

1. **Progressive Enhancement**: Both `recurrence.forms.RecurrenceWidget` and `django_recur.widgets.JSCalendarRecurrenceWidget` render a standard `<textarea class="recurrence-widget">` wrapped inside `<django-recur-widget data-output-format="...">`.
2. **Encapsulated Shadow DOM UI**: When `recurrence-widget.js` loads in the browser, `<django-recur-widget>` upgrades automatically, attaches an open Shadow DOM, hides the underlying `<textarea>` visually, and renders an accessible interactive builder for:
   - **Inclusion & Exclusion Rules (`recurrenceRules` / `excludedRecurrenceRules`)**: Frequency (`yearly`, `monthly`, `weekly`, `daily`, `hourly`, `minutely`, `secondly`), interval, weekday chips (`mo`–`su`), relative `NDay` (`nthOfPeriod`, e.g., `1st Monday`, `Last Friday`), month-day lists (`byMonthDay`), months (`byMonth`), RFC 8984 `skip` strategy (`omit`, `backward`, `forward`), and end conditions (`count` or `until`).
   - **Inclusion & Exclusion Dates (`recurrenceOverrides` / `RDATE` / `EXDATE`)**: Interactive date picker for adding one-off inclusion or exclusion dates.
   - **Live Human-Readable Summary & Format Inspector**: Displays a live summary of each rule alongside a collapsible RFC 8984 JSON / RFC 5545 `RRULE` inspector.
3. **Dual Output Serialization**:
   - When `data-output-format="rfc5545"` (default for `RecurrenceWidget`), the synced `<textarea>` receives RFC 5545 `RRULE` / `EXRULE` / `RDATE` / `EXDATE` text.
   - When `data-output-format="rfc8984"` (default for `JSCalendarRecurrenceWidget`), the synced `<textarea>` receives RFC 8984 JSCalendar JSON.
   - Regardless of the output format, the widget can **parse both RFC 8984 JSON and RFC 5545 text** as its initial value.

---

## Using the Widget in Django Forms & Admin

The widget is automatically attached to `RecurrenceField` and `JSCalendarRecurrenceField`. You can also customize it explicitly on any Django form:

```python
from django import forms
from django_recur.forms import JSCalendarRecurrenceFormField
from django_recur.widgets import JSCalendarRecurrenceWidget, RecurrenceWidget


class EventForm(forms.Form):
    # Emits RFC 8984 JSCalendar JSON
    schedule = JSCalendarRecurrenceFormField(
        widget=JSCalendarRecurrenceWidget(attrs={"class": "custom-schedule"})
    )
```

Remember to include `{{ form.media }}` in templates outside the Django Admin:

```html
{{ form.media }}
<form method="post">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit">Save</button>
</form>
```

---

## Custom Events & DOM API

`<django-recur-widget>` dispatches a bubbling, composed CustomEvent named `django-recur:change` whenever rules or overrides are modified:

```javascript
document.addEventListener("django-recur:change", (event) => {
    console.log("RFC 8984 JSCalendar state:", event.detail.jscalendar);
    console.log("Serialized form value:", event.detail.serialized);
});
```

You can also read or update the widget state programmatically in JavaScript/TypeScript:

```javascript
const widget = document.querySelector("django-recur-widget");

// Read the current RFC 8984 JSCalendarRecurrenceData object
const state = widget.value;

// Update the widget state programmatically
widget.value = {
    "@type": "JSCalendarRecurrence",
    recurrenceRules: [
        {
            "@type": "RecurrenceRule",
            frequency: "weekly",
            interval: 1,
            byDay: [{ "@type": "NDay", day: "mo" }, { "@type": "NDay", day: "fr" }],
        },
    ],
};
```

---

## Styling & Dark Mode (CSS Custom Properties)

`<django-recur-widget>` inherits Django Admin's CSS variables (`--body-bg`, `--body-fg`, `--border-color`, `--primary`, `--delete-button-bg`) out of the box, and exposes dedicated custom properties for custom themes:

```css
django-recur-widget {
    --django-recur-bg: #ffffff;
    --django-recur-fg: #1f2937;
    --django-recur-border: #d1d5db;
    --django-recur-primary: #2563eb;
    --django-recur-danger: #dc2626;
    --django-recur-muted: #6b7280;
    --django-recur-card-bg: #f9fafb;
}
```

---

## Building and Testing the Frontend Pipeline

The TypeScript source lives in `frontend/`:

```bash
cd frontend
npm install

# Run TypeScript typechecking
npm run typecheck

# Run Vitest unit & DOM tests
npm test

# Build production bundle into src/recurrence/static/recurrence/js/recurrence-widget.js
npm run build
```
