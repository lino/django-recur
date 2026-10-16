import { describe, expect, it } from "vitest";
import {
  deserializeSchedule,
  parseICalendar,
  ruleToText,
  serializeScheduleToJSCalendar,
  serializeToICalendar,
} from "../src/codec";
import { DjRecurrenceWidget, registerRecurrenceWebComponent } from "../src/widget-element";

describe("RFC 8984 & RFC 5545 TypeScript Codec", () => {
  it("parses RFC 5545 RRULE and converts to canonical RFC 8984 JSCalendar", () => {
    const schedule = parseICalendar(
      "DTSTART:20260101T090000Z\nRRULE:FREQ=MONTHLY;INTERVAL=2;BYDAY=-1FR;COUNT=6\nEXDATE:20260327T090000Z"
    );
    const jscal = serializeScheduleToJSCalendar(schedule);
    expect(jscal["@type"]).toBe("Event");
    expect(jscal.start).toBe("2026-01-01T09:00:00Z");
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
      "2026-03-27T09:00:00Z": { excluded: true },
    });

    const roundtripped = serializeToICalendar(jscal);
    expect(roundtripped).toContain("RRULE:FREQ=MONTHLY;INTERVAL=2;COUNT=6;BYDAY=-1FR");
    expect(roundtripped).toContain("EXDATE:20260327T090000Z");
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

describe("<dj-recurrence-widget> Web Component", () => {
  it("upgrades a textarea and synchronizes RFC 8984 and RFC 5545 values", () => {
    registerRecurrenceWebComponent();
    document.body.innerHTML = `
      <dj-recurrence-widget data-output-format="rfc8984">
        <textarea id="id_schedule" class="recurrence-widget">RRULE:FREQ=WEEKLY;BYDAY=MO,WE</textarea>
      </dj-recurrence-widget>
    `;
    const widget = document.querySelector("dj-recurrence-widget") as DjRecurrenceWidget;
    const textarea = document.getElementById("id_schedule") as HTMLTextAreaElement;

    expect(widget.getJSCalendar().recurrenceRules?.[0]?.frequency).toBe("weekly");
    widget.addDate(new Date(Date.UTC(2026, 4, 10)));
    expect(textarea.value).toContain('"recurrenceOverrides"');
  });
});
