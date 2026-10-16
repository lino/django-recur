/**
 * TypeScript definitions for RFC 8984 (JSCalendar) recurrence rules and overrides.
 */

export type FrequencyName =
  | "yearly"
  | "monthly"
  | "weekly"
  | "daily"
  | "hourly"
  | "minutely"
  | "secondly";

export type DayOfWeekName = "mo" | "tu" | "we" | "th" | "fr" | "sa" | "su";

export type SkipMode = "omit" | "backward" | "forward";

export interface JSCalendarNDay {
  "@type"?: "NDay";
  day: DayOfWeekName;
  nthOfPeriod?: number;
}

export interface JSCalendarRecurrenceRule {
  "@type"?: "RecurrenceRule";
  frequency: FrequencyName;
  interval?: number;
  rscale?: string;
  skip?: SkipMode;
  firstDayOfWeek?: DayOfWeekName;
  byDay?: JSCalendarNDay[];
  byMonthDay?: number[];
  byMonth?: string[];
  byYearDay?: number[];
  byWeekNo?: number[];
  byHour?: number[];
  byMinute?: number[];
  bySecond?: number[];
  bySetPosition?: number[];
  count?: number;
  until?: string;
}

export interface JSCalendarOverridePatch {
  excluded?: boolean;
  [key: string]: unknown;
}

export interface JSCalendarSchedule {
  "@type": "Event";
  start?: string;
  dtend?: string;
  timeZone?: string;
  includeDtstart?: boolean;
  recurrenceRules?: JSCalendarRecurrenceRule[];
  excludedRecurrenceRules?: JSCalendarRecurrenceRule[];
  recurrenceOverrides?: Record<string, JSCalendarOverridePatch>;
}

export type OutputFormat = "rfc8984" | "rfc5545";

export interface WidgetOptions {
  defaultFreq?: FrequencyName;
  outputFormat?: OutputFormat;
  showSkipSelector?: boolean;
}
