/**
 * Bidirectional RFC 8984 (JSCalendar) <-> RFC 5545 (iCalendar) codec and
 * human-readable text formatter for the <django-recur-widget> Web Component.
 */

import type {
  DayOfWeekName,
  FrequencyName,
  JSCalendarNDay,
  JSCalendarOverridePatch,
  JSCalendarRecurrenceRule,
  JSCalendarSchedule,
  SkipMode,
} from "./types";

export const FREQUENCIES: readonly FrequencyName[] = [
  "yearly",
  "monthly",
  "weekly",
  "daily",
  "hourly",
  "minutely",
  "secondly",
] as const;

export const WEEKDAYS: readonly DayOfWeekName[] = [
  "mo",
  "tu",
  "we",
  "th",
  "fr",
  "sa",
  "su",
] as const;

declare global {
  interface Window {
    gettext?: (msgid: string) => string;
    pgettext?: (context: string, msgid: string) => string;
    interpolate?: (
      fmt: string,
      obj: Record<string, unknown> | unknown[],
      named?: boolean
    ) => string;
    recurrence?: Record<string, unknown>;
    django?: { jQuery?: unknown };
  }
}

export function t(msgid: string): string {
  if (typeof window !== "undefined" && typeof window.gettext === "function") {
    return window.gettext(msgid);
  }
  return msgid;
}

export function pt(context: string, msgid: string): string {
  if (typeof window !== "undefined" && typeof window.pgettext === "function") {
    return window.pgettext(context, msgid);
  }
  return msgid;
}

export function interp(fmt: string, namedObj: Record<string, string | number>): string {
  if (typeof window !== "undefined" && typeof window.interpolate === "function") {
    return window.interpolate(fmt, namedObj, true);
  }
  return fmt.replace(/%\((\w+)\)s/g, (_, key: string) => String(namedObj[key] ?? ""));
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function pad4(n: number): string {
  return String(n).padStart(4, "0");
}

export function dateToJSCalendarUTC(dt: Date): string {
  return (
    `${pad4(dt.getUTCFullYear())}-${pad2(dt.getUTCMonth() + 1)}-${pad2(dt.getUTCDate())}` +
    `T${pad2(dt.getUTCHours())}:${pad2(dt.getUTCMinutes())}:${pad2(dt.getUTCSeconds())}Z`
  );
}

export function dateToICalendarUTC(dt: Date): string {
  return (
    `${pad4(dt.getUTCFullYear())}${pad2(dt.getUTCMonth() + 1)}${pad2(dt.getUTCDate())}` +
    `T${pad2(dt.getUTCHours())}${pad2(dt.getUTCMinutes())}${pad2(dt.getUTCSeconds())}Z`
  );
}

export function parseDateString(text: string): Date {
  // Treat floating wall times as UTC only for component access and arithmetic.
  const cleaned = text.trim().toUpperCase();
  const match = /^(\d{4})-?(\d{2})-?(\d{2})(?:T(\d{2}):?(\d{2}):?(\d{2})(\.\d+)?Z?)?$/.exec(cleaned);
  if (!match) throw new Error(`Invalid date-time: ${text}`);
  const [, year, month, day, hour = "00", minute = "00", second = "00", fraction = ""] = match;
  const iso = `${year}-${month}-${day}T${hour}:${minute}:${second}`;
  const date = new Date(`${iso}${fraction}Z`);
  if (!Number.isFinite(date.getTime()) || dateToJSCalendarUTC(date).slice(0, -1) !== iso) {
    throw new Error(`Invalid date-time: ${text}`);
  }
  return date;
}

function zoneOffset(date: Date, timeZone: string): number {
  const formatter = new Intl.DateTimeFormat("en", { timeZone, timeZoneName: "longOffset" });
  const name = formatter.formatToParts(date).find(({ type }) => type === "timeZoneName")?.value;
  if (name === "GMT") return 0;
  const match = /^GMT([+-])(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(name ?? "");
  if (!match) throw new Error(`Unknown offset for ${timeZone}`);
  const [, sign, h, m, s = "0"] = match;
  return (sign === "-" ? -1 : 1) * (Number(h) * 3600 + Number(m) * 60 + Number(s)) * 1000;
}

function wallTimeToUTC(wallTime: Date, timeZone: string): Date {
  const ms = wallTime.getTime();
  const day = 86_400_000;
  const before = zoneOffset(new Date(ms - day), timeZone);
  const after = zoneOffset(new Date(ms + day), timeZone);
  const candidates = [before, after].map((offset) => new Date(ms - offset));
  return candidates
    .filter((date) => date.getTime() + zoneOffset(date, timeZone) === ms)
    .sort((a, b) => a.getTime() - b.getTime())[0] ?? candidates[0];
}

export function parseNDayToken(token: string | number | JSCalendarNDay): JSCalendarNDay {
  if (typeof token === "object" && token !== null && "day" in token) {
    const day = String(token.day).toLowerCase() as DayOfWeekName;
    const res: JSCalendarNDay = { "@type": "NDay", day };
    if (token.nthOfPeriod && token.nthOfPeriod !== 0) {
      res.nthOfPeriod = Number(token.nthOfPeriod);
    }
    return res;
  }
  if (typeof token === "number") {
    const day = WEEKDAYS[token];
    if (!day) throw new Error(`Invalid weekday index: ${token}`);
    return { "@type": "NDay", day };
  }
  const str = String(token).trim();
  if (/^\d$/.test(str)) {
    const idx = Number.parseInt(str, 10);
    const day = WEEKDAYS[idx];
    if (!day) throw new Error(`Invalid weekday index: ${str}`);
    return { "@type": "NDay", day };
  }
  const dayPart = str.slice(-2).toLowerCase() as DayOfWeekName;
  if (!WEEKDAYS.includes(dayPart)) {
    throw new Error(`Invalid weekday token: ${str}`);
  }
  const nthPart = str.slice(0, -2);
  if (!nthPart) {
    return { "@type": "NDay", day: dayPart };
  }
  const nth = Number.parseInt(nthPart, 10);
  if (Number.isNaN(nth) || nth === 0) {
    throw new Error(`Invalid nthOfPeriod in weekday token: ${str}`);
  }
  return { "@type": "NDay", day: dayPart, nthOfPeriod: nth };
}

export function formatNDayICalendar(nday: JSCalendarNDay): string {
  const code = nday.day.toUpperCase();
  if (nday.nthOfPeriod && nday.nthOfPeriod !== 0) {
    return `${nday.nthOfPeriod}${code}`;
  }
  return code;
}

export function canonicalizeRule(rule: JSCalendarRecurrenceRule): JSCalendarRecurrenceRule {
  const out: JSCalendarRecurrenceRule = {
    "@type": "RecurrenceRule",
    frequency: rule.frequency,
  };
  if (rule.interval && rule.interval !== 1) out.interval = rule.interval;
  if (rule.rscale && rule.rscale !== "gregorian") out.rscale = rule.rscale;
  if (rule.skip && rule.skip !== "omit") out.skip = rule.skip;
  if (rule.firstDayOfWeek && rule.firstDayOfWeek !== "mo") {
    out.firstDayOfWeek = rule.firstDayOfWeek;
  }
  if (rule.byDay && rule.byDay.length > 0) {
    out.byDay = rule.byDay.map((d) => parseNDayToken(d));
  }
  if (rule.byMonthDay && rule.byMonthDay.length > 0) {
    out.byMonthDay = [...rule.byMonthDay];
  }
  if (rule.byMonth && rule.byMonth.length > 0) {
    out.byMonth = rule.byMonth.map(String);
  }
  if (rule.byYearDay && rule.byYearDay.length > 0) out.byYearDay = [...rule.byYearDay];
  if (rule.byWeekNo && rule.byWeekNo.length > 0) out.byWeekNo = [...rule.byWeekNo];
  if (rule.byHour && rule.byHour.length > 0) out.byHour = [...rule.byHour];
  if (rule.byMinute && rule.byMinute.length > 0) out.byMinute = [...rule.byMinute];
  if (rule.bySecond && rule.bySecond.length > 0) out.bySecond = [...rule.bySecond];
  if (rule.bySetPosition && rule.bySetPosition.length > 0) {
    out.bySetPosition = [...rule.bySetPosition];
  }
  if (rule.count != null) {
    out.count = Number(rule.count);
  } else if (rule.until) {
    out.until = rule.until;
  }
  return out;
}

export function serializeToICalendar(schedule: JSCalendarSchedule): string {
  const lines: string[] = [];
  const timeZone = schedule.timeZone;
  const serializeDate = (name: string, value: string): string => {
    const date = parseDateString(value);
    const compact = dateToICalendarUTC(date);
    if (value.endsWith("Z") || timeZone === "UTC") return `${name}:${compact}`;
    const property = timeZone ? `${name};TZID=${timeZone}` : name;
    return `${property}:${compact.slice(0, -1)}`;
  };

  if (schedule.start) {
    lines.push(serializeDate("DTSTART", schedule.start));
  }
  if (schedule.dtend) {
    lines.push(serializeDate("DTEND", schedule.dtend));
  }

  const serializeRule = (rule: JSCalendarRecurrenceRule): string => {
    const parts: string[] = [`FREQ=${rule.frequency.toUpperCase()}`];
    if (rule.rscale) parts.unshift(`RSCALE=${rule.rscale.toUpperCase()}`);
    if (rule.skip) {
      if (!rule.rscale) parts.unshift("RSCALE=GREGORIAN");
      parts.push(`SKIP=${rule.skip.toUpperCase()}`);
    }
    if (rule.interval && rule.interval !== 1) {
      parts.push(`INTERVAL=${rule.interval}`);
    }
    if (rule.firstDayOfWeek && rule.firstDayOfWeek !== "mo") {
      parts.push(`WKST=${rule.firstDayOfWeek.toUpperCase()}`);
    }
    if (rule.count != null) {
      parts.push(`COUNT=${rule.count}`);
    } else if (rule.until) {
      const date = parseDateString(rule.until);
      const utc = rule.until.endsWith("Z") || timeZone === "UTC";
      const until = utc ? dateToICalendarUTC(date)
        : timeZone ? dateToICalendarUTC(wallTimeToUTC(date, timeZone))
        : dateToICalendarUTC(date).slice(0, -1);
      parts.push(`UNTIL=${until}`);
    }
    if (rule.byDay && rule.byDay.length > 0) {
      parts.push(`BYDAY=${rule.byDay.map(formatNDayICalendar).join(",")}`);
    }
    if (rule.bySetPosition && rule.bySetPosition.length > 0) {
      parts.push(`BYSETPOS=${rule.bySetPosition.join(",")}`);
    }
    if (rule.byMonth && rule.byMonth.length > 0) {
      parts.push(`BYMONTH=${rule.byMonth.join(",")}`);
    }
    if (rule.byMonthDay && rule.byMonthDay.length > 0) {
      parts.push(`BYMONTHDAY=${rule.byMonthDay.join(",")}`);
    }
    if (rule.byYearDay && rule.byYearDay.length > 0) {
      parts.push(`BYYEARDAY=${rule.byYearDay.join(",")}`);
    }
    if (rule.byWeekNo && rule.byWeekNo.length > 0) {
      parts.push(`BYWEEKNO=${rule.byWeekNo.join(",")}`);
    }
    if (rule.byHour && rule.byHour.length > 0) {
      parts.push(`BYHOUR=${rule.byHour.join(",")}`);
    }
    if (rule.byMinute && rule.byMinute.length > 0) {
      parts.push(`BYMINUTE=${rule.byMinute.join(",")}`);
    }
    if (rule.bySecond && rule.bySecond.length > 0) {
      parts.push(`BYSECOND=${rule.bySecond.join(",")}`);
    }
    return parts.join(";");
  };

  for (const r of schedule.recurrenceRules ?? []) {
    lines.push(`RRULE:${serializeRule(r)}`);
  }
  for (const ex of schedule.excludedRecurrenceRules ?? []) {
    lines.push(`EXRULE:${serializeRule(ex)}`);
  }
  for (const [dtStr, patch] of Object.entries(schedule.recurrenceOverrides ?? {})) {
    lines.push(serializeDate(patch.excluded ? "EXDATE" : "RDATE", dtStr));
  }
  return lines.join("\n");
}

export function parseICalendar(text: string): JSCalendarSchedule {
  const schedule: JSCalendarSchedule = {
    "@type": "Event",
    recurrenceRules: [],
    excludedRecurrenceRules: [],
    recurrenceOverrides: {},
  };
  if (!text || !text.trim()) {
    return schedule;
  }

  const pattern = /^(DTSTART|DTEND|RRULE|EXRULE|RDATE|EXDATE)((?:;[^:\r\n]+)?):([^\r\n]*)/gim;
  const matches = [...text.replace(/\r?\n[ \t]/g, "").matchAll(pattern)];
  if (matches.length === 0) throw new Error("No recurrence properties found");
  const tzid = (parameters: string): string | undefined => {
    const match = /(?:^|;)TZID=(?:"([^"]+)"|([^;]+))/i.exec(parameters);
    return match?.[1] ?? match?.[2];
  };
  const dated = matches.filter(([, label]) => !/^(EX|R)RULE$/i.test(label));
  const firstDate = dated.find(([, label]) => label.toUpperCase() === "DTSTART") ?? dated[0];
  if (firstDate) {
    schedule.timeZone = tzid(firstDate[2]) ??
      (firstDate[3].split(",")[0].trim().toUpperCase().endsWith("Z") ? "UTC" : undefined);
  } else if (matches.some(([, , , value]) => /(?:^|;)UNTIL=\d{8}T\d{6}Z(?:;|$)/i.test(value))) {
    schedule.timeZone = "UTC";
  }
  const localDate = (value: string, params = ""): string => {
    const date = parseDateString(value);
    const target = schedule.timeZone;
    const source = value.trim().toUpperCase().endsWith("Z") ? "UTC" : tzid(params);
    if (source === target) {
      if (source && source !== "UTC") zoneOffset(date, source);
      return dateToJSCalendarUTC(date).slice(0, -1);
    }
    if (!source || !target) throw new Error("Cannot mix floating and timezone-bound dates");
    const instant = source === "UTC" ? date : wallTimeToUTC(date, source);
    const wallTime = new Date(instant.getTime() + zoneOffset(instant, target));
    if (wallTimeToUTC(wallTime, target).getTime() !== instant.getTime()) {
      throw new Error("Cannot represent the later occurrence of an ambiguous local time");
    }
    return dateToJSCalendarUTC(wallTime).slice(0, -1);
  };

  for (const match of matches) {
    const label = match[1].toUpperCase();
    const parameters = match[2];
    const paramText = match[3].trim();
    if (!paramText) continue;

    if (label === "RRULE" || label === "EXRULE") {
      const rule: JSCalendarRecurrenceRule = {
        "@type": "RecurrenceRule",
        frequency: "weekly",
      };
      for (const token of paramText.split(";")) {
        if (!token) continue;
        const [rawKey, rawVal] = token.split("=", 2);
        if (!rawKey || rawVal === undefined) continue;
        const key = rawKey.trim().toUpperCase();
        const values = rawVal.split(",").map((v) => v.trim());

        if (key === "FREQ") {
          const f = values[0].toLowerCase() as FrequencyName;
          if (FREQUENCIES.includes(f)) rule.frequency = f;
        } else if (key === "INTERVAL") {
          rule.interval = Number.parseInt(values[0], 10) || 1;
        } else if (key === "WKST") {
          rule.firstDayOfWeek = parseNDayToken(values[0]).day;
        } else if (key === "SKIP") {
          rule.skip = values[0].toLowerCase() as SkipMode;
        } else if (key === "RSCALE") {
          rule.rscale = values[0].toLowerCase();
        } else if (key === "COUNT") {
          rule.count = Number.parseInt(values[0], 10);
        } else if (key === "UNTIL") {
          rule.until = localDate(values[0]);
        } else if (key === "BYDAY") {
          rule.byDay = values.map((v) => parseNDayToken(v));
        } else if (key === "BYMONTH") {
          rule.byMonth = values.map((v) => v.toUpperCase());
        } else if (key === "BYMONTHDAY") {
          rule.byMonthDay = values.map((v) => Number.parseInt(v, 10));
        } else if (key === "BYYEARDAY") {
          rule.byYearDay = values.map((v) => Number.parseInt(v, 10));
        } else if (key === "BYWEEKNO") {
          rule.byWeekNo = values.map((v) => Number.parseInt(v, 10));
        } else if (key === "BYHOUR") {
          rule.byHour = values.map((v) => Number.parseInt(v, 10));
        } else if (key === "BYMINUTE") {
          rule.byMinute = values.map((v) => Number.parseInt(v, 10));
        } else if (key === "BYSECOND") {
          rule.bySecond = values.map((v) => Number.parseInt(v, 10));
        } else if (key === "BYSETPOS") {
          rule.bySetPosition = values.map((v) => Number.parseInt(v, 10));
        }
      }
      if (label === "RRULE") {
        schedule.recurrenceRules!.push(canonicalizeRule(rule));
      } else {
        schedule.excludedRecurrenceRules!.push(canonicalizeRule(rule));
      }
    } else if (label === "DTSTART") {
      schedule.start = localDate(paramText, parameters);
    } else if (label === "DTEND") {
      schedule.dtend = localDate(paramText, parameters);
    } else if (label === "RDATE") {
      for (const item of paramText.split(",")) {
        const key = localDate(item, parameters);
        schedule.recurrenceOverrides![key] ??= {};
      }
    } else if (label === "EXDATE") {
      for (const item of paramText.split(",")) {
        const key = localDate(item, parameters);
        schedule.recurrenceOverrides![key] = { excluded: true };
      }
    }
  }

  return schedule;
}

export function deserializeSchedule(input: string | Record<string, unknown>): JSCalendarSchedule {
  if (typeof input === "object" && input !== null) {
    return normalizeScheduleObject(input);
  }
  const trimmed = String(input ?? "").trim();
  if (!trimmed) {
    return {
      "@type": "Event",
      recurrenceRules: [],
      excludedRecurrenceRules: [],
      recurrenceOverrides: {},
    };
  }
  if (trimmed.startsWith("{")) {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    return normalizeScheduleObject(parsed);
  }
  return parseICalendar(trimmed);
}

function normalizeScheduleObject(raw: Record<string, unknown>): JSCalendarSchedule {
  if (raw["@type"] === "RecurrenceRule" || ("frequency" in raw && !("recurrenceRules" in raw))) {
    return {
      "@type": "Event",
      recurrenceRules: [canonicalizeRule(raw as unknown as JSCalendarRecurrenceRule)],
      excludedRecurrenceRules: [],
      recurrenceOverrides: {},
    };
  }
  const rrules = Array.isArray(raw.recurrenceRules)
    ? (raw.recurrenceRules as JSCalendarRecurrenceRule[]).map(canonicalizeRule)
    : [];
  const exrules = Array.isArray(raw.excludedRecurrenceRules)
    ? (raw.excludedRecurrenceRules as JSCalendarRecurrenceRule[]).map(canonicalizeRule)
    : [];
  const overrides: Record<string, JSCalendarOverridePatch> = {};
  if (raw.recurrenceOverrides && typeof raw.recurrenceOverrides === "object") {
    for (const [k, v] of Object.entries(raw.recurrenceOverrides as Record<string, unknown>)) {
      parseDateString(k);
      overrides[k] = (v as JSCalendarOverridePatch) ?? {};
    }
  }
  const start = typeof raw.start === "string" ? raw.start : undefined;
  const dtend = typeof raw.dtend === "string" ? raw.dtend : undefined;
  const timeZone = typeof raw.timeZone === "string" ? raw.timeZone : undefined;
  for (const date of [start, dtend, ...[...rrules, ...exrules].map((rule) => rule.until)]) {
    if (date) parseDateString(date);
  }
  if (timeZone) new Intl.DateTimeFormat("en", { timeZone });

  return {
    ...raw,
    "@type": "Event",
    start,
    dtend,
    timeZone,
    includeDtstart: typeof raw.includeDtstart === "boolean" ? raw.includeDtstart : undefined,
    recurrenceRules: rrules,
    excludedRecurrenceRules: exrules,
    recurrenceOverrides: overrides,
  };
}

export function serializeScheduleToJSCalendar(schedule: JSCalendarSchedule): JSCalendarSchedule {
  const { recurrenceRules, excludedRecurrenceRules, recurrenceOverrides, ...properties } = schedule;
  const out: JSCalendarSchedule = { ...properties, "@type": "Event" };
  if (schedule.start) out.start = schedule.start;
  if (schedule.dtend) out.dtend = schedule.dtend;
  if (schedule.timeZone) out.timeZone = schedule.timeZone;
  if (recurrenceRules?.length) {
    out.recurrenceRules = recurrenceRules.map(canonicalizeRule);
  }
  if (excludedRecurrenceRules?.length) {
    out.excludedRecurrenceRules = excludedRecurrenceRules.map(canonicalizeRule);
  }
  if (recurrenceOverrides && Object.keys(recurrenceOverrides).length > 0) {
    out.recurrenceOverrides = { ...recurrenceOverrides };
  }
  return out;
}

const FREQ_LABELS = [
  "annually",
  "monthly",
  "weekly",
  "daily",
  "hourly",
  "minutely",
  "secondly",
] as const;

const INTERVAL_PLURAL = [
  "years",
  "months",
  "weeks",
  "days",
  "hours",
  "minutes",
  "seconds",
] as const;

const WEEKDAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

const MONTH_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

const POSITION_LABELS: Record<string, string> = {
  "1": "first %(weekday)s",
  "2": "second %(weekday)s",
  "3": "third %(weekday)s",
  "4": "fourth %(weekday)s",
  "-1": "last %(weekday)s",
  "-2": "second last %(weekday)s",
  "-3": "third last %(weekday)s",
};

const LAST_OF_MONTH_LABELS: Record<string, string> = {
  "-1": "last",
  "-2": "second last",
  "-3": "third last",
  "-4": "fourth last",
};

function ordinalDay(day: number): string {
  if (day < 0) {
    return t(LAST_OF_MONTH_LABELS[String(day)] ?? String(day));
  }
  if (day === 11 || day === 12 || day === 13) return `${day}th`;
  const rem = day % 10;
  if (rem === 1) return `${day}st`;
  if (rem === 2) return `${day}nd`;
  if (rem === 3) return `${day}rd`;
  return `${day}th`;
}

export function ruleToText(rule: JSCalendarRecurrenceRule, short = false): string {
  const freqIdx = Math.max(0, FREQUENCIES.indexOf(rule.frequency));
  const parts: string[] = [];
  const interval = rule.interval ?? 1;

  if (interval > 1) {
    parts.push(
      interp(t("every %(number)s %(freq)s"), {
        number: interval,
        freq: t(INTERVAL_PLURAL[freqIdx]),
      })
    );
  } else {
    parts.push(t(FREQ_LABELS[freqIdx]));
  }

  const getWeekdayName = (dayCode: DayOfWeekName): string => {
    const idx = Math.max(0, WEEKDAYS.indexOf(dayCode));
    return short ? t(WEEKDAY_SHORT[idx]) : t(WEEKDAY_NAMES[idx]);
  };

  const formatPositionalWeekdays = (): string => {
    const items: string[] = [];
    const byDay = rule.byDay ?? [];
    const bySetPos = rule.bySetPosition ?? [];
    if (bySetPos.length > 0 && byDay.length > 0) {
      for (const pos of bySetPos) {
        const tpl = t(POSITION_LABELS[String(pos)] ?? "%(weekday)s");
        for (const nd of byDay) {
          items.push(interp(tpl, { weekday: getWeekdayName(nd.day) }));
        }
      }
    } else {
      for (const nd of byDay) {
        const pos = nd.nthOfPeriod ?? 1;
        const tpl = t(POSITION_LABELS[String(pos)] ?? "%(weekday)s");
        items.push(interp(tpl, { weekday: getWeekdayName(nd.day) }));
      }
    }
    return items.join(", ");
  };

  if (rule.frequency === "yearly") {
    if (rule.byMonth && rule.byMonth.length > 0) {
      const mNames = rule.byMonth.map((m) => {
        const idx = Number.parseInt(String(m).replace("L", ""), 10) - 1;
        return short ? t(MONTH_SHORT[idx] ?? m) : t(MONTH_NAMES[idx] ?? m);
      });
      parts.push(interp(t("each %(items)s"), { items: mNames.join(", ") }));
    }
    if ((rule.byDay && rule.byDay.length > 0) || (rule.bySetPosition && rule.bySetPosition.length > 0)) {
      parts.push(interp(t("on the %(items)s"), { items: formatPositionalWeekdays() }));
    }
  } else if (rule.frequency === "monthly") {
    if (rule.byMonthDay && rule.byMonthDay.length > 0) {
      const dNames = rule.byMonthDay.map(ordinalDay);
      parts.push(interp(t("on the %(items)s"), { items: dNames.join(", ") }));
    } else if (rule.byDay && rule.byDay.length > 0) {
      parts.push(interp(t("on the %(items)s"), { items: formatPositionalWeekdays() }));
    }
  } else if (rule.frequency === "weekly") {
    if (rule.byDay && rule.byDay.length > 0) {
      const wNames = rule.byDay.map((nd) => getWeekdayName(nd.day));
      parts.push(interp(t("each %(items)s"), { items: wNames.join(", ") }));
    }
  }

  if (rule.count != null && rule.count > 0) {
    if (rule.count === 1) {
      parts.push(t("occuring once"));
    } else {
      parts.push(interp(t("occuring %(number)s times"), { number: rule.count }));
    }
  } else if (rule.until) {
    const dt = parseDateString(rule.until);
    const ymd = `${pad4(dt.getUTCFullYear())}-${pad2(dt.getUTCMonth() + 1)}-${pad2(dt.getUTCDate())}`;
    parts.push(interp(t("until %(date)s"), { date: ymd }));
  }

  return parts.join(", ");
}
