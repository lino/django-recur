/**
 * Legacy window.recurrence compatibility bridge and MutationObserver for
 * Django Admin inline formsets.
 */

import {
  deserializeSchedule,
  FREQUENCIES,
  parseNDayToken,
  ruleToText,
  serializeScheduleToJSCalendar,
  serializeToICalendar,
  WEEKDAYS,
} from "./codec";
import type { DayOfWeekName, FrequencyName, JSCalendarRecurrenceRule } from "./types";
import { DjRecurrenceWidget, registerRecurrenceWebComponent } from "./widget-element";

export function upgradeRecurrenceTextareas(root: ParentNode = document): void {
  registerRecurrenceWebComponent();
  const textareas = root.querySelectorAll<HTMLTextAreaElement>(
    'textarea.recurrence-widget:not([id*="__prefix__"])'
  );
  textareas.forEach((textarea) => {
    if (textarea.closest("dj-recurrence-widget")) {
      return;
    }
    if (textarea.dataset.djUpgraded === "true") {
      return;
    }
    textarea.dataset.djUpgraded = "true";
    const wrapper = document.createElement("dj-recurrence-widget") as DjRecurrenceWidget;
    const outputFormat = textarea.getAttribute("data-output-format") || "rfc5545";
    wrapper.setAttribute("data-output-format", outputFormat);
    const parent = textarea.parentNode;
    if (parent) {
      parent.insertBefore(wrapper, textarea);
      wrapper.appendChild(textarea);
      wrapper.attachTextarea(textarea);
    }
  });
}

export function initRecurrenceWidget(target?: HTMLElement | { attr?: (k: string) => string }): void {
  registerRecurrenceWebComponent();
  if (!target) {
    upgradeRecurrenceTextareas(document);
    return;
  }
  if (typeof (target as { attr?: (k: string) => string }).attr === "function") {
    const id = (target as { attr: (k: string) => string }).attr("id");
    const el = id ? document.getElementById(id) : null;
    if (el && el.tagName === "TEXTAREA") {
      upgradeRecurrenceTextareas(el.parentElement ?? document);
    }
    return;
  }
  if (target instanceof HTMLElement) {
    upgradeRecurrenceTextareas(target);
  }
}

export function installLegacyRecurrenceNamespace(): void {
  if (typeof window === "undefined") return;

  class LegacyWeekday {
    number: number;
    index: number | null;
    constructor(number: number, index: number | null = null) {
      this.number = number;
      this.index = index || null;
    }
    with_index(index: number): LegacyWeekday {
      return new LegacyWeekday(this.number, index);
    }
    toString(): string {
      const code = WEEKDAYS[this.number]?.toUpperCase() ?? "MO";
      return this.index ? `${this.index}${code}` : code;
    }
  }

  class LegacyRule {
    freq: number;
    interval: number;
    wkst: number | null;
    count: number | null;
    until: Date | null;
    byday: LegacyWeekday[];
    bymonth: number[];
    bymonthday: number[];
    byyearday: number[];
    byweekno: number[];
    byhour: number[];
    byminute: number[];
    bysecond: number[];
    bysetpos: number[];

    constructor(freq: number, options: Record<string, unknown> = {}) {
      this.freq = freq;
      this.interval = Number(options.interval ?? 1);
      this.wkst = (options.wkst as number) ?? null;
      this.count = (options.count as number) ?? null;
      this.until = (options.until as Date) ?? null;
      this.byday = Array.isArray(options.byday) ? (options.byday as LegacyWeekday[]) : [];
      this.bymonth = Array.isArray(options.bymonth) ? (options.bymonth as number[]) : [];
      this.bymonthday = Array.isArray(options.bymonthday)
        ? (options.bymonthday as number[])
        : [];
      this.byyearday = Array.isArray(options.byyearday)
        ? (options.byyearday as number[])
        : [];
      this.byweekno = Array.isArray(options.byweekno) ? (options.byweekno as number[]) : [];
      this.byhour = Array.isArray(options.byhour) ? (options.byhour as number[]) : [];
      this.byminute = Array.isArray(options.byminute) ? (options.byminute as number[]) : [];
      this.bysecond = Array.isArray(options.bysecond) ? (options.bysecond as number[]) : [];
      this.bysetpos = Array.isArray(options.bysetpos) ? (options.bysetpos as number[]) : [];
    }

    toJSCalendarRule(): JSCalendarRecurrenceRule {
      const freqName: FrequencyName = FREQUENCIES[this.freq] ?? "weekly";
      return {
        "@type": "RecurrenceRule",
        frequency: freqName,
        interval: this.interval,
        firstDayOfWeek:
          this.wkst != null ? (WEEKDAYS[this.wkst] as DayOfWeekName) : undefined,
        count: this.count ?? undefined,
        until: this.until ? this.until.toISOString() : undefined,
        byDay: this.byday.map((d) => parseNDayToken(String(d))),
        byMonth: this.bymonth.map(String),
        byMonthDay: this.bymonthday,
        byYearDay: this.byyearday,
        byWeekNo: this.byweekno,
        byHour: this.byhour,
        byMinute: this.byminute,
        bySecond: this.bysecond,
        bySetPosition: this.bysetpos,
      };
    }

    get_display_text(short = false): string {
      return ruleToText(this.toJSCalendarRule(), short);
    }
  }

  const legacyNamespace: Record<string, unknown> = {
    YEARLY: 0,
    MONTHLY: 1,
    WEEKLY: 2,
    DAILY: 3,
    HOURLY: 4,
    MINUTELY: 5,
    SECONDLY: 6,
    Weekday: LegacyWeekday,
    Rule: LegacyRule,
    serialize: (input: unknown, format: "rfc5545" | "rfc8984" = "rfc5545"): string => {
      if (input instanceof LegacyRule) {
        const sched = {
          "@type": "Event" as const,
          recurrenceRules: [input.toJSCalendarRule()],
        };
        return format === "rfc8984"
          ? JSON.stringify(serializeScheduleToJSCalendar(sched))
          : serializeToICalendar(sched);
      }
      const sched = deserializeSchedule(input as string | Record<string, unknown>);
      return format === "rfc8984"
        ? JSON.stringify(serializeScheduleToJSCalendar(sched))
        : serializeToICalendar(sched);
    },
    deserialize: deserializeSchedule,
    widget: {
      Widget: function (textareaOrId: string | HTMLTextAreaElement) {
        const el =
          typeof textareaOrId === "string"
            ? (document.getElementById(textareaOrId) as HTMLTextAreaElement | null)
            : textareaOrId;
        if (el) {
          upgradeRecurrenceTextareas(el.parentElement ?? document);
        }
      },
      textareas_to_widgets: () => upgradeRecurrenceTextareas(document),
    },
  };

  window.recurrence = Object.assign(window.recurrence ?? {}, legacyNamespace);
  (window as unknown as Record<string, unknown>).initRecurrenceWidget = initRecurrenceWidget;
}

export function setupDomObserver(): void {
  if (typeof document === "undefined" || typeof MutationObserver === "undefined") return;

  const ready = (): void => {
    upgradeRecurrenceTextareas(document);
    const targetNode = document.getElementById("container") ?? document.body;
    if (!targetNode) return;
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.type === "childList" && m.addedNodes.length > 0) {
          m.addedNodes.forEach((node) => {
            if (node instanceof HTMLElement) {
              upgradeRecurrenceTextareas(node);
            }
          });
        }
      }
    });
    observer.observe(targetNode, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
}
