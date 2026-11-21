import { describe, expect, it } from "vitest";
import calendarCases from "../../tests/calendar_cases.json";
import {
  deserializeSchedule,
  parseICalendar,
  ruleToText,
  serializeScheduleToJSCalendar,
  serializeToICalendar,
} from "../src/codec";
import { DjangoRecurWidget, registerRecurrenceWebComponent } from "../src/widget-element";

describe("RFC 8984 & RFC 5545 TypeScript Codec", () => {
  it("parses RFC 5545 RRULE and converts to canonical RFC 8984 JSCalendar", () => {
    const schedule = parseICalendar(
      "DTSTART:20260101T090000Z\nRRULE:FREQ=MONTHLY;INTERVAL=2;BYDAY=-1FR;COUNT=6\nEXDATE:20260327T090000Z"
    );
    const jscal = serializeScheduleToJSCalendar(schedule);
    expect(jscal["@type"]).toBe("Event");
    expect(jscal.start).toBe("2026-01-01T09:00:00");
    expect(jscal.timeZone).toBe("UTC");
    expect(jscal.recurrenceRules).toEqual([
      {
        "@type": "RecurrenceRule",
        frequency: "monthly",
        interval: 2,
        byDay: [{ "@type": "NDay", day: "fr", nthOfPeriod: -1 }],
        count: 6,
      },
    ]);
    expect(jscal.recurrenceOverrides).toEqual({
      "2026-03-27T09:00:00": { excluded: true },
    });

    const roundtripped = serializeToICalendar(jscal);
    expect(roundtripped).toContain("RRULE:FREQ=MONTHLY;INTERVAL=2;COUNT=6;BYDAY=-1FR");
    expect(roundtripped).toContain("EXDATE:20260327T090000Z");
  });

  it("unfolds iCalendar, preserves TZID, and gives EXDATE precedence", () => {
    const fixture = calendarCases.foldedBerlin;
    const schedule = parseICalendar(fixture.icalendar);
    expect(serializeScheduleToJSCalendar(schedule)).toEqual(fixture.jscalendar);
    const text = serializeToICalendar(schedule);
    expect(text).toContain("DTSTART;TZID=Europe/Berlin:20260322T090000");
    expect(text).toContain("EXDATE;TZID=Europe/Berlin:20260405T090000");
  });

  it.each(calendarCases.localUntil)("$description", ({ zone, local, utc }) => {
    const schedule = deserializeSchedule({
      "@type": "Event",
      timeZone: zone,
      start: local,
      recurrenceRules: [{ frequency: "daily", until: local }],
    });
    expect(serializeToICalendar(schedule)).toContain(`UNTIL=${utc}`);
  });

  it("round-trips floating times independently of the browser timezone", () => {
    const text = "DTSTART:20000229T090000\nRRULE:FREQ=DAILY;UNTIL=20000301T090000";
    expect(serializeToICalendar(parseICalendar(text))).toEqual(text);
  });

  it.each(["19000229T090000", "21000229T090000", "20161231T235960Z"])(
    "rejects an unrepresentable date-time %s", (value) => {
      expect(() => parseICalendar(`DTSTART:${value}`)).toThrow("Invalid date-time");
    }
  );

  it("round-trips a leap-second rule without interpreting it as a JS Date", () => {
    const text = "DTSTART:20161231T235959Z\nRRULE:FREQ=MINUTELY;BYSECOND=59,60";
    expect(serializeToICalendar(parseICalendar(text))).toBe(text);
  });

  it("renders natural language rule descriptions", () => {
    expect(
      ruleToText({
        "@type": "RecurrenceRule",
        frequency: "weekly",
        byDay: [{ "@type": "NDay", day: "tu" }],
      })
    ).toBe("weekly, each Tuesday");

    expect(
      ruleToText({
        "@type": "RecurrenceRule",
        frequency: "yearly",
        interval: 2,
        byMonth: ["1", "6"],
        count: 3,
      })
    ).toBe("every 2 years, each January, June, occuring 3 times");
  });
});

describe("<django-recur-widget> Web Component", () => {
  it("upgrades a textarea and synchronizes RFC 8984 and RFC 5545 values", () => {
    registerRecurrenceWebComponent();
    document.body.innerHTML = `
      <django-recur-widget data-output-format="rfc8984">
        <textarea id="id_schedule" class="recurrence-widget">RRULE:FREQ=WEEKLY;BYDAY=MO,WE</textarea>
      </django-recur-widget>
    `;
    const widget = document.querySelector("django-recur-widget") as DjangoRecurWidget;
    const textarea = document.getElementById("id_schedule") as HTMLTextAreaElement;

    expect(widget.getJSCalendar().recurrenceRules?.[0]?.frequency).toBe("weekly");
    widget.addDate(new Date(Date.UTC(2026, 4, 10)));
    expect(textarea.value).toContain('"recurrenceOverrides"');
  });

  it("preserves override patches and local identifiers when adding a rule", () => {
    registerRecurrenceWebComponent();
    const value = {
      ...calendarCases.foldedBerlin.jscalendar,
      includeDtstart: false,
      recurrenceOverrides: { "2026-04-05T09:00:00": { title: "Moved", start: "2026-04-05T10:15:00" } },
    };
    const widget = document.createElement("django-recur-widget") as DjangoRecurWidget;
    widget.dataset.outputFormat = "rfc8984";
    const textarea = document.createElement("textarea");
    textarea.value = JSON.stringify(value);
    widget.appendChild(textarea);
    document.body.appendChild(widget);

    widget.addRule({ frequency: "daily" });

    expect(JSON.parse(textarea.value)).toEqual({
      ...value,
      recurrenceRules: [...value.recurrenceRules, { "@type": "RecurrenceRule", frequency: "daily" }],
    });
  });

  it("leaves malformed input available in the original textarea", () => {
    registerRecurrenceWebComponent();
    document.body.innerHTML = "<django-recur-widget><textarea>{malformed</textarea></django-recur-widget>";
    const textarea = document.querySelector("textarea")!;
    expect(textarea.value).toBe("{malformed");
    expect(textarea.style.display).toBe("");
  });
});
