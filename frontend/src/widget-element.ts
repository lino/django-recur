/**
 * <django-recur-widget> Custom Element (Web Component) for Django forms & Admin.
 *
 * Progressively enhances a <textarea class="recurrence-widget"> element, manages
 * state internally as an RFC 8984 JSCalendar schedule, and synchronizes either
 * RFC 8984 JSON or RFC 5545 iCalendar output to the underlying textarea.
 */

import {
  dateToJSCalendarUTC,
  deserializeSchedule,
  FREQUENCIES,
  pad2,
  pad4,
  parseDateString,
  ruleToText,
  serializeScheduleToJSCalendar,
  serializeToICalendar,
  t,
  WEEKDAYS,
} from "./codec";
import type {
  DayOfWeekName,
  FrequencyName,
  JSCalendarOverridePatch,
  JSCalendarRecurrenceRule,
  JSCalendarSchedule,
  OutputFormat,
  SkipMode,
} from "./types";

interface RulePanelEntry {
  excluded: boolean;
  rule: JSCalendarRecurrenceRule;
  expanded: boolean;
}

interface DatePanelEntry {
  isoKey: string;
  excluded: boolean;
  patch: JSCalendarOverridePatch;
  expanded: boolean;
}

const MONTH_SHORT_LABELS = [
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

const WEEKDAY_SHORT_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;
const WEEKDAY_FULL_LABELS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
] as const;

const POSITIONS: readonly { value: number; label: string }[] = [
  { value: 1, label: "first" },
  { value: 2, label: "second" },
  { value: 3, label: "third" },
  { value: 4, label: "fourth" },
  { value: -1, label: "last" },
  { value: -2, label: "second last" },
  { value: -3, label: "third last" },
];

export class DjangoRecurWidget extends HTMLElement {
  private textarea: HTMLTextAreaElement | null = null;
  private uiRoot: HTMLDivElement | null = null;
  private schedule: JSCalendarSchedule = {
    "@type": "Event",
    recurrenceRules: [],
    excludedRecurrenceRules: [],
    recurrenceOverrides: {},
  };
  private rulePanels: RulePanelEntry[] = [];
  private datePanels: DatePanelEntry[] = [];
  private outputFormat: OutputFormat = "rfc5545";
  private initialized = false;

  static get observedAttributes(): string[] {
    return ["data-output-format"];
  }

  connectedCallback(): void {
    if (this.initialized) return;
    this.initialized = true;
    this.setup();
  }

  attributeChangedCallback(name: string, oldVal: string | null, newVal: string | null): void {
    if (name === "data-output-format" && oldVal !== newVal && newVal) {
      this.outputFormat = newVal === "rfc8984" ? "rfc8984" : "rfc5545";
      this.syncToTextarea();
    }
  }

  public attachTextarea(textarea: HTMLTextAreaElement): void {
    this.textarea = textarea;
    if (!this.initialized) {
      this.initialized = true;
      this.setup();
    }
  }

  private setup(): void {
    if (!this.textarea) {
      this.textarea = this.querySelector("textarea");
    }
    if (!this.textarea) {
      this.textarea = document.createElement("textarea");
      this.textarea.className = "recurrence-widget";
      this.appendChild(this.textarea);
    }

    const attrFormat =
      this.getAttribute("data-output-format") ||
      this.textarea.getAttribute("data-output-format");
    if (attrFormat === "rfc8984") {
      this.outputFormat = "rfc8984";
    } else if (this.textarea.value.trim().startsWith("{")) {
      this.outputFormat = "rfc8984";
    } else {
      this.outputFormat = "rfc5545";
    }

    try {
      this.loadFromValue(this.textarea.value);
    } catch {
      return;
    }
    this.textarea.classList.add("recurrence-widget", "hidden");
    this.textarea.style.display = "none";

    this.uiRoot = document.createElement("div");
    this.uiRoot.className = "django-recur-container recurrence-widget";
    this.insertBefore(this.uiRoot, this.textarea);

    this.renderUI();
  }

  public loadFromValue(rawValue: string): void {
    this.schedule = deserializeSchedule(rawValue);
    this.rulePanels = [];
    for (const r of this.schedule.recurrenceRules ?? []) {
      this.rulePanels.push({ excluded: false, rule: r, expanded: false });
    }
    for (const ex of this.schedule.excludedRecurrenceRules ?? []) {
      this.rulePanels.push({ excluded: true, rule: ex, expanded: false });
    }
    this.datePanels = [];
    for (const [isoKey, patch] of Object.entries(this.schedule.recurrenceOverrides ?? {})) {
      this.datePanels.push({
        isoKey,
        excluded: Boolean(patch.excluded),
        patch,
        expanded: false,
      });
    }
  }

  public getJSCalendar(): JSCalendarSchedule {
    this.rebuildScheduleFromPanels();
    return serializeScheduleToJSCalendar(this.schedule);
  }

  public getICalendar(): string {
    this.rebuildScheduleFromPanels();
    return serializeToICalendar(this.schedule);
  }

  private rebuildScheduleFromPanels(): void {
    this.schedule.recurrenceRules = this.rulePanels
      .filter((p) => !p.excluded)
      .map((p) => p.rule);
    this.schedule.excludedRecurrenceRules = this.rulePanels
      .filter((p) => p.excluded)
      .map((p) => p.rule);
    const overrides: Record<string, JSCalendarOverridePatch> = {};
    for (const dp of this.datePanels) {
      if (dp.excluded === Boolean(dp.patch.excluded)) {
        overrides[dp.isoKey] = dp.patch;
      } else {
        overrides[dp.isoKey] = dp.excluded ? { excluded: true } : {};
      }
    }
    this.schedule.recurrenceOverrides = overrides;
  }

  private syncToTextarea(): void {
    if (!this.textarea) return;
    const jscal = this.getJSCalendar();
    const ical = serializeToICalendar(this.schedule);
    if (this.outputFormat === "rfc8984") {
      const hasContent =
        Boolean(jscal.start) ||
        Boolean(jscal.dtend) ||
        jscal.includeDtstart === false ||
        Boolean(jscal.recurrenceRules?.length) ||
        Boolean(jscal.excludedRecurrenceRules?.length) ||
        Boolean(jscal.recurrenceOverrides && Object.keys(jscal.recurrenceOverrides).length);
      this.textarea.value = hasContent ? JSON.stringify(jscal) : "";
    } else {
      this.textarea.value = ical;
    }

    this.textarea.dispatchEvent(new Event("input", { bubbles: true }));
    this.textarea.dispatchEvent(new Event("change", { bubbles: true }));
    this.dispatchEvent(
      new CustomEvent("django-recur:change", {
        bubbles: true,
        detail: {
          jscalendar: jscal,
          icalendar: ical,
          outputFormat: this.outputFormat,
        },
      })
    );
  }

  public addRule(rule?: Partial<JSCalendarRecurrenceRule>): void {
    for (const p of this.rulePanels) p.expanded = false;
    for (const d of this.datePanels) d.expanded = false;
    const newRule: JSCalendarRecurrenceRule = {
      "@type": "RecurrenceRule",
      frequency: rule?.frequency ?? "weekly",
      interval: rule?.interval ?? 1,
      skip: rule?.skip ?? "omit",
      byDay: rule?.byDay ? [...rule.byDay] : [],
      byMonth: rule?.byMonth ? [...rule.byMonth] : [],
      byMonthDay: rule?.byMonthDay ? [...rule.byMonthDay] : [],
      count: rule?.count,
      until: rule?.until,
    };
    this.rulePanels.push({ excluded: false, rule: newRule, expanded: true });
    this.syncToTextarea();
    this.renderUI();
  }

  public addDate(dt?: Date): void {
    for (const p of this.rulePanels) p.expanded = false;
    for (const d of this.datePanels) d.expanded = false;
    const target = dt ?? new Date();
    const utcMidnight = new Date(
      Date.UTC(target.getFullYear(), target.getMonth(), target.getDate(), 0, 0, 0)
    );
    this.datePanels.push({
      isoKey: dateToJSCalendarUTC(utcMidnight).slice(0, -1),
      excluded: false,
      patch: {},
      expanded: true,
    });
    this.syncToTextarea();
    this.renderUI();
  }

  private renderUI(): void {
    if (!this.uiRoot) return;
    this.uiRoot.innerHTML = "";

    const panelsContainer = document.createElement("div");
    panelsContainer.className = "panels";

    this.rulePanels.forEach((entry, idx) => {
      panelsContainer.appendChild(this.renderRulePanel(entry, idx));
    });

    this.datePanels.forEach((entry, idx) => {
      panelsContainer.appendChild(this.renderDatePanel(entry, idx));
    });

    const controlBar = document.createElement("div");
    controlBar.className = "control";

    const addRuleBtn = document.createElement("button");
    addRuleBtn.type = "button";
    addRuleBtn.className = "add-button add-rule";
    addRuleBtn.innerHTML = `<span class="plus">+</span><span class="recurrence-label">${t("Add rule")}</span>`;
    addRuleBtn.addEventListener("click", () => this.addRule());

    const addDateBtn = document.createElement("button");
    addDateBtn.type = "button";
    addDateBtn.className = "add-button add-date";
    addDateBtn.innerHTML = `<span class="plus">+</span><span class="recurrence-label">${t("Add date")}</span>`;
    addDateBtn.addEventListener("click", () => this.addDate());

    const badge = document.createElement("span");
    badge.className = "django-recur-badge";
    badge.textContent = this.outputFormat === "rfc8984" ? "RFC 8984" : "RFC 5545";

    controlBar.appendChild(addRuleBtn);
    controlBar.appendChild(addDateBtn);
    controlBar.appendChild(badge);

    this.uiRoot.appendChild(panelsContainer);
    this.uiRoot.appendChild(controlBar);
  }

  private renderRulePanel(entry: RulePanelEntry, index: number): HTMLElement {
    const panel = document.createElement("div");
    panel.className = `panel ${entry.excluded ? "exclusion" : "inclusion"}`;

    const header = document.createElement("div");
    header.className = "header";

    const removeBtn = document.createElement("a");
    removeBtn.className = "remove";
    removeBtn.href = "javascript:void(0)";
    removeBtn.title = t("Remove");
    removeBtn.innerHTML = "&times;";
    removeBtn.addEventListener("click", () => {
      this.rulePanels.splice(index, 1);
      this.syncToTextarea();
      this.renderUI();
    });

    const labelLink = document.createElement("a");
    labelLink.className = "recurrence-label";
    labelLink.href = "javascript:void(0)";
    const updateHeaderLabel = (): void => {
      const desc = ruleToText(entry.rule);
      const prefix = entry.excluded ? `${t("excluding")} ` : "";
      const full = prefix + desc;
      labelLink.textContent = full.charAt(0).toUpperCase() + full.slice(1);
    };
    updateHeaderLabel();

    labelLink.addEventListener("click", () => {
      entry.expanded = !entry.expanded;
      this.renderUI();
    });

    header.appendChild(removeBtn);
    header.appendChild(labelLink);
    panel.appendChild(header);

    const body = document.createElement("div");
    body.className = `body ${entry.expanded ? "" : "hidden"}`;

    const formContainer = document.createElement("div");
    formContainer.className = "dj-rule-form";

    // 1. Exclusion checkbox
    const modeRow = document.createElement("div");
    modeRow.className = "mode";
    const modeCheckbox = document.createElement("input");
    modeCheckbox.type = "checkbox";
    modeCheckbox.className = "checkbox";
    modeCheckbox.checked = entry.excluded;
    const modeLabel = document.createElement("span");
    modeLabel.className = "recurrence-label";
    modeLabel.textContent = t("Exclude these occurences");
    modeCheckbox.addEventListener("change", () => {
      entry.excluded = modeCheckbox.checked;
      updateHeaderLabel();
      this.syncToTextarea();
    });
    modeRow.appendChild(modeCheckbox);
    modeRow.appendChild(modeLabel);
    formContainer.appendChild(modeRow);

    // 2. Frequency & Interval & RFC 8984 Skip row
    const topControls = document.createElement("div");
    topControls.className = "dj-rule-top-controls";

    const freqContainer = document.createElement("div");
    freqContainer.className = "freq";
    const freqLabel = document.createElement("span");
    freqLabel.className = "recurrence-label";
    freqLabel.textContent = `${t("Frequency")}:`;
    const freqSelect = document.createElement("select");
    freqSelect.name = "freq";
    const selectableFreqs: { value: FrequencyName; label: string }[] = [
      { value: "yearly", label: t("Annually") },
      { value: "monthly", label: t("Monthly") },
      { value: "weekly", label: t("Weekly") },
      { value: "daily", label: t("Daily") },
    ];
    for (const opt of selectableFreqs) {
      const optionEl = document.createElement("option");
      optionEl.value = opt.value;
      optionEl.textContent = opt.label;
      if (entry.rule.frequency === opt.value) optionEl.selected = true;
      freqSelect.appendChild(optionEl);
    }
    freqSelect.addEventListener("change", () => {
      entry.rule.frequency = freqSelect.value as FrequencyName;
      this.syncToTextarea();
      this.renderUI();
    });
    freqContainer.appendChild(freqLabel);
    freqContainer.appendChild(freqSelect);

    const intervalContainer = document.createElement("div");
    intervalContainer.className = "interval";
    const intervalPrefix = document.createElement("span");
    intervalPrefix.className = "recurrence-label";
    intervalPrefix.textContent = t("Every");
    const intervalInput = document.createElement("input");
    intervalInput.type = "number";
    intervalInput.min = "1";
    intervalInput.size = 2;
    intervalInput.value = String(entry.rule.interval ?? 1);
    const intervalSuffix = document.createElement("span");
    intervalSuffix.className = "recurrence-unit-label";
    const unitNames: Record<FrequencyName, [string, string]> = {
      yearly: [t("year"), t("years")],
      monthly: [t("month"), t("months")],
      weekly: [t("week"), t("weeks")],
      daily: [t("day"), t("days")],
      hourly: [t("hour"), t("hours")],
      minutely: [t("minute"), t("minutes")],
      secondly: [t("second"), t("seconds")],
    };
    const updateIntervalUnit = (): void => {
      const pair = unitNames[entry.rule.frequency] ?? ["unit", "units"];
      intervalSuffix.textContent = (entry.rule.interval ?? 1) > 1 ? pair[1] : pair[0];
    };
    updateIntervalUnit();
    intervalInput.addEventListener("change", () => {
      const parsed = Number.parseInt(intervalInput.value, 10);
      entry.rule.interval = Number.isNaN(parsed) || parsed < 1 ? 1 : parsed;
      intervalInput.value = String(entry.rule.interval);
      updateIntervalUnit();
      updateHeaderLabel();
      this.syncToTextarea();
    });
    intervalContainer.appendChild(intervalPrefix);
    intervalContainer.appendChild(intervalInput);
    intervalContainer.appendChild(intervalSuffix);

    topControls.appendChild(freqContainer);
    topControls.appendChild(intervalContainer);

    if (entry.rule.frequency === "yearly" || entry.rule.frequency === "monthly") {
      const skipContainer = document.createElement("div");
      skipContainer.className = "skip-control";
      const skipLabel = document.createElement("span");
      skipLabel.className = "recurrence-label";
      skipLabel.textContent = `${t("Invalid dates (RFC 8984 skip)")}:`;
      const skipSelect = document.createElement("select");
      skipSelect.name = "skip";
      for (const sVal of ["omit", "backward", "forward"] as SkipMode[]) {
        const opt = document.createElement("option");
        opt.value = sVal;
        opt.textContent = sVal;
        if ((entry.rule.skip ?? "omit") === sVal) opt.selected = true;
        skipSelect.appendChild(opt);
      }
      skipSelect.addEventListener("change", () => {
        entry.rule.skip = skipSelect.value as SkipMode;
        this.syncToTextarea();
      });
      skipContainer.appendChild(skipLabel);
      skipContainer.appendChild(skipSelect);
      topControls.appendChild(skipContainer);
    }

    formContainer.appendChild(topControls);

    // 3. Frequency-specific section
    const freqDetails = document.createElement("div");
    freqDetails.className = "form";
    if (entry.rule.frequency === "yearly") {
      freqDetails.appendChild(this.renderYearlySection(entry, updateHeaderLabel));
    } else if (entry.rule.frequency === "monthly") {
      freqDetails.appendChild(this.renderMonthlySection(entry, updateHeaderLabel));
    } else if (entry.rule.frequency === "weekly") {
      freqDetails.appendChild(this.renderWeeklySection(entry, updateHeaderLabel));
    }
    formContainer.appendChild(freqDetails);

    // 4. Limit section (Until / Count)
    formContainer.appendChild(this.renderLimitSection(entry, updateHeaderLabel));

    body.appendChild(formContainer);
    panel.appendChild(body);
    return panel;
  }

  private renderYearlySection(
    entry: RulePanelEntry,
    onUpdateLabel: () => void
  ): HTMLElement {
    const wrapper = document.createElement("div");
    wrapper.className = "yearly";

    const table = document.createElement("table");
    table.className = "grid";
    const tbody = document.createElement("tbody");
    const activeMonths = new Set((entry.rule.byMonth ?? []).map(String));

    for (let r = 0; r < 3; r++) {
      const tr = document.createElement("tr");
      for (let c = 0; c < 4; c++) {
        const mNum = r * 4 + c + 1;
        const mKey = String(mNum);
        const td = document.createElement("td");
        td.textContent = t(MONTH_SHORT_LABELS[mNum - 1]);
        if (activeMonths.has(mKey)) td.classList.add("active");
        td.addEventListener("click", () => {
          if (activeMonths.has(mKey)) {
            activeMonths.delete(mKey);
            td.classList.remove("active");
          } else {
            activeMonths.add(mKey);
            td.classList.add("active");
          }
          entry.rule.byMonth = Array.from(activeMonths).sort(
            (a, b) => Number.parseInt(a, 10) - Number.parseInt(b, 10)
          );
          onUpdateLabel();
          this.syncToTextarea();
        });
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    wrapper.appendChild(table);

    const bydayRow = document.createElement("div");
    bydayRow.className = "byday";
    const bydayCheck = document.createElement("input");
    bydayCheck.type = "checkbox";
    bydayCheck.className = "checkbox";
    bydayCheck.checked = Boolean(entry.rule.byDay && entry.rule.byDay.length > 0);
    const bydayLabel = document.createElement("span");
    bydayLabel.className = "recurrence-label";
    bydayLabel.textContent = `${t("On the")}:`;
    bydayRow.appendChild(bydayCheck);
    bydayRow.appendChild(bydayLabel);

    const posSelect = document.createElement("select");
    posSelect.name = "position";
    for (const p of POSITIONS) {
      const opt = document.createElement("option");
      opt.value = String(p.value);
      opt.textContent = t(p.label);
      if ((entry.rule.byDay?.[0]?.nthOfPeriod ?? 1) === p.value) opt.selected = true;
      posSelect.appendChild(opt);
    }

    const daySelect = document.createElement("select");
    daySelect.name = "weekday";
    WEEKDAYS.forEach((dCode, idx) => {
      const opt = document.createElement("option");
      opt.value = dCode;
      opt.textContent = t(WEEKDAY_FULL_LABELS[idx]);
      if ((entry.rule.byDay?.[0]?.day ?? "mo") === dCode) opt.selected = true;
      daySelect.appendChild(opt);
    });

    posSelect.disabled = !bydayCheck.checked;
    daySelect.disabled = !bydayCheck.checked;

    const syncYearlyByDay = (): void => {
      if (bydayCheck.checked) {
        posSelect.disabled = false;
        daySelect.disabled = false;
        entry.rule.byDay = [
          {
            "@type": "NDay",
            day: daySelect.value as DayOfWeekName,
            nthOfPeriod: Number.parseInt(posSelect.value, 10),
          },
        ];
      } else {
        posSelect.disabled = true;
        daySelect.disabled = true;
        entry.rule.byDay = [];
      }
      onUpdateLabel();
      this.syncToTextarea();
    };

    bydayCheck.addEventListener("change", syncYearlyByDay);
    posSelect.addEventListener("change", syncYearlyByDay);
    daySelect.addEventListener("change", syncYearlyByDay);

    const posSection = document.createElement("div");
    posSection.className = "section";
    posSection.appendChild(posSelect);
    posSection.appendChild(daySelect);

    wrapper.appendChild(bydayRow);
    wrapper.appendChild(posSection);
    return wrapper;
  }

  private renderMonthlySection(
    entry: RulePanelEntry,
    onUpdateLabel: () => void
  ): HTMLElement {
    const wrapper = document.createElement("div");
    wrapper.className = "monthly";
    const list = document.createElement("ul");
    list.className = "monthly";

    const usingWeekday = Boolean(
      entry.rule.byDay && entry.rule.byDay.length > 0 && !(entry.rule.byMonthDay?.length)
    );

    // Option A: monthday grid
    const monthdayLi = document.createElement("li");
    monthdayLi.className = "monthday";
    const monthdayRadio = document.createElement("input");
    monthdayRadio.type = "radio";
    monthdayRadio.className = "radio";
    monthdayRadio.checked = !usingWeekday;
    const monthdayLabel = document.createElement("span");
    monthdayLabel.className = "recurrence-label";
    monthdayLabel.textContent = `${t("Each")}:`;

    const gridSection = document.createElement("div");
    gridSection.className = "section";
    const table = document.createElement("table");
    table.className = "grid";
    const tbody = document.createElement("tbody");
    const activeMonthDays = new Set<number>(entry.rule.byMonthDay ?? []);

    let cellNum = 0;
    for (let r = 0; r < 5; r++) {
      const tr = document.createElement("tr");
      for (let c = 0; c < 7; c++) {
        cellNum += 1;
        const dayVal = cellNum <= 31 ? cellNum : cellNum - 36;
        const td = document.createElement("td");
        td.textContent = String(dayVal);
        if (activeMonthDays.has(dayVal)) td.classList.add("active");
        td.addEventListener("click", () => {
          if (!monthdayRadio.checked) return;
          if (activeMonthDays.has(dayVal)) {
            activeMonthDays.delete(dayVal);
            td.classList.remove("active");
          } else {
            activeMonthDays.add(dayVal);
            td.classList.add("active");
          }
          entry.rule.byDay = [];
          entry.rule.byMonthDay = Array.from(activeMonthDays);
          onUpdateLabel();
          this.syncToTextarea();
        });
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    gridSection.appendChild(table);
    monthdayLi.appendChild(monthdayRadio);
    monthdayLi.appendChild(monthdayLabel);
    monthdayLi.appendChild(gridSection);

    // Option B: Nth weekday
    const weekdayLi = document.createElement("li");
    weekdayLi.className = "weekday";
    const weekdayRadio = document.createElement("input");
    weekdayRadio.type = "radio";
    weekdayRadio.className = "radio";
    weekdayRadio.checked = usingWeekday;
    const weekdayLabel = document.createElement("span");
    weekdayLabel.className = "recurrence-label";
    weekdayLabel.textContent = `${t("On the")}:`;

    const posSelect = document.createElement("select");
    for (const p of POSITIONS) {
      const opt = document.createElement("option");
      opt.value = String(p.value);
      opt.textContent = t(p.label);
      if ((entry.rule.byDay?.[0]?.nthOfPeriod ?? 1) === p.value) opt.selected = true;
      posSelect.appendChild(opt);
    }
    const daySelect = document.createElement("select");
    WEEKDAYS.forEach((dCode, idx) => {
      const opt = document.createElement("option");
      opt.value = dCode;
      opt.textContent = t(WEEKDAY_FULL_LABELS[idx]);
      if ((entry.rule.byDay?.[0]?.day ?? "mo") === dCode) opt.selected = true;
      daySelect.appendChild(opt);
    });

    posSelect.disabled = !usingWeekday;
    daySelect.disabled = !usingWeekday;

    const syncMonthlyMode = (mode: "monthday" | "weekday"): void => {
      if (mode === "monthday") {
        monthdayRadio.checked = true;
        weekdayRadio.checked = false;
        posSelect.disabled = true;
        daySelect.disabled = true;
        entry.rule.byDay = [];
        entry.rule.byMonthDay = Array.from(activeMonthDays);
      } else {
        weekdayRadio.checked = true;
        monthdayRadio.checked = false;
        posSelect.disabled = false;
        daySelect.disabled = false;
        entry.rule.byMonthDay = [];
        entry.rule.byDay = [
          {
            "@type": "NDay",
            day: daySelect.value as DayOfWeekName,
            nthOfPeriod: Number.parseInt(posSelect.value, 10),
          },
        ];
      }
      onUpdateLabel();
      this.syncToTextarea();
    };

    monthdayRadio.addEventListener("change", () => syncMonthlyMode("monthday"));
    weekdayRadio.addEventListener("change", () => syncMonthlyMode("weekday"));
    posSelect.addEventListener("change", () => syncMonthlyMode("weekday"));
    daySelect.addEventListener("change", () => syncMonthlyMode("weekday"));

    const wdSection = document.createElement("div");
    wdSection.className = "section";
    wdSection.appendChild(posSelect);
    wdSection.appendChild(daySelect);

    weekdayLi.appendChild(weekdayRadio);
    weekdayLi.appendChild(weekdayLabel);
    weekdayLi.appendChild(wdSection);

    list.appendChild(monthdayLi);
    list.appendChild(weekdayLi);
    wrapper.appendChild(list);
    return wrapper;
  }

  private renderWeeklySection(
    entry: RulePanelEntry,
    onUpdateLabel: () => void
  ): HTMLElement {
    const wrapper = document.createElement("div");
    wrapper.className = "weekly";
    const section = document.createElement("div");
    section.className = "section";

    const table = document.createElement("table");
    table.className = "grid";
    const tr = document.createElement("tr");
    const activeDays = new Set<DayOfWeekName>((entry.rule.byDay ?? []).map((d) => d.day));

    WEEKDAYS.forEach((dCode, idx) => {
      const td = document.createElement("td");
      td.textContent = t(WEEKDAY_SHORT_LABELS[idx]);
      if (activeDays.has(dCode)) td.classList.add("active");
      td.addEventListener("click", () => {
        if (activeDays.has(dCode)) {
          activeDays.delete(dCode);
          td.classList.remove("active");
        } else {
          activeDays.add(dCode);
          td.classList.add("active");
        }
        entry.rule.byDay = WEEKDAYS.filter((d) => activeDays.has(d)).map((day) => ({
          "@type": "NDay",
          day,
        }));
        onUpdateLabel();
        this.syncToTextarea();
      });
      tr.appendChild(td);
    });

    const tbody = document.createElement("tbody");
    tbody.appendChild(tr);
    table.appendChild(tbody);
    section.appendChild(table);
    wrapper.appendChild(section);
    return wrapper;
  }

  private renderLimitSection(
    entry: RulePanelEntry,
    onUpdateLabel: () => void
  ): HTMLElement {
    const limitContainer = document.createElement("div");
    limitContainer.className = "limit";

    const hasLimit = entry.rule.count != null || Boolean(entry.rule.until);
    const usingCount = entry.rule.count != null;

    const limitCheck = document.createElement("input");
    limitCheck.type = "checkbox";
    limitCheck.className = "checkbox";
    limitCheck.checked = hasLimit;

    const limitLabel = document.createElement("span");
    limitLabel.className = "recurrence-label";
    limitLabel.textContent = `${t("Repeat until")}:`;

    const ul = document.createElement("ul");
    ul.className = `until-count ${hasLimit ? "" : "disabled"}`;

    // Until date option
    const untilLi = document.createElement("li");
    untilLi.className = "until";
    const untilRadio = document.createElement("input");
    untilRadio.type = "radio";
    untilRadio.className = "radio";
    untilRadio.checked = !usingCount;
    untilRadio.disabled = !hasLimit;
    const untilText = document.createElement("span");
    untilText.className = "recurrence-label";
    untilText.textContent = `${t("Date")}:`;
    const untilDateInput = document.createElement("input");
    untilDateInput.type = "date";
    untilDateInput.className = "date-field";
    untilDateInput.disabled = !hasLimit || usingCount;
    if (entry.rule.until) {
      const dt = parseDateString(entry.rule.until);
      untilDateInput.value = `${pad4(dt.getUTCFullYear())}-${pad2(dt.getUTCMonth() + 1)}-${pad2(dt.getUTCDate())}`;
    } else {
      const today = new Date();
      untilDateInput.value = `${pad4(today.getFullYear())}-${pad2(today.getMonth() + 1)}-${pad2(today.getDate())}`;
    }
    untilLi.appendChild(untilRadio);
    untilLi.appendChild(untilText);
    untilLi.appendChild(untilDateInput);

    // Count option
    const countLi = document.createElement("li");
    countLi.className = "count";
    const countRadio = document.createElement("input");
    countRadio.type = "radio";
    countRadio.className = "radio";
    countRadio.checked = usingCount;
    countRadio.disabled = !hasLimit;
    const countInput = document.createElement("input");
    countInput.type = "number";
    countInput.min = "1";
    countInput.size = 2;
    countInput.value = String(entry.rule.count ?? 1);
    countInput.disabled = !hasLimit || !usingCount;
    const countLabel = document.createElement("span");
    countLabel.className = "recurrence-label";
    countLabel.textContent = t("occurrences");
    countLi.appendChild(countRadio);
    countLi.appendChild(countInput);
    countLi.appendChild(countLabel);

    const syncLimit = (): void => {
      if (!limitCheck.checked) {
        ul.classList.add("disabled");
        untilRadio.disabled = true;
        countRadio.disabled = true;
        untilDateInput.disabled = true;
        countInput.disabled = true;
        delete entry.rule.count;
        delete entry.rule.until;
      } else {
        ul.classList.remove("disabled");
        untilRadio.disabled = false;
        countRadio.disabled = false;
        if (countRadio.checked) {
          untilDateInput.disabled = true;
          countInput.disabled = false;
          delete entry.rule.until;
          const c = Number.parseInt(countInput.value, 10);
          entry.rule.count = Number.isNaN(c) || c < 1 ? 1 : c;
        } else {
          untilDateInput.disabled = false;
          countInput.disabled = true;
          delete entry.rule.count;
          if (untilDateInput.value) {
            const date = dateToJSCalendarUTC(parseDateString(untilDateInput.value));
            entry.rule.until = entry.rule.until
              ? date.slice(0, 10) + entry.rule.until.slice(10)
              : date.slice(0, -1);
          }
        }
      }
      onUpdateLabel();
      this.syncToTextarea();
    };

    limitCheck.addEventListener("change", syncLimit);
    untilRadio.addEventListener("change", () => {
      untilRadio.checked = true;
      countRadio.checked = false;
      syncLimit();
    });
    countRadio.addEventListener("change", () => {
      countRadio.checked = true;
      untilRadio.checked = false;
      syncLimit();
    });
    untilDateInput.addEventListener("change", syncLimit);
    countInput.addEventListener("change", syncLimit);

    ul.appendChild(untilLi);
    ul.appendChild(countLi);
    limitContainer.appendChild(limitCheck);
    limitContainer.appendChild(limitLabel);
    limitContainer.appendChild(ul);
    return limitContainer;
  }

  private renderDatePanel(entry: DatePanelEntry, index: number): HTMLElement {
    const panel = document.createElement("div");
    panel.className = `panel ${entry.excluded ? "exclusion" : "inclusion"}`;

    const header = document.createElement("div");
    header.className = "header";

    const removeBtn = document.createElement("a");
    removeBtn.className = "remove";
    removeBtn.href = "javascript:void(0)";
    removeBtn.title = t("Remove");
    removeBtn.innerHTML = "&times;";
    removeBtn.addEventListener("click", () => {
      this.datePanels.splice(index, 1);
      this.syncToTextarea();
      this.renderUI();
    });

    const labelLink = document.createElement("a");
    labelLink.className = "recurrence-label";
    labelLink.href = "javascript:void(0)";
    const updateDateLabel = (): void => {
      const dt = parseDateString(entry.isoKey);
      const ymd = `${pad4(dt.getUTCFullYear())}-${pad2(dt.getUTCMonth() + 1)}-${pad2(dt.getUTCDate())}`;
      labelLink.textContent = entry.excluded ? `${t("Excluding")} ${ymd}` : ymd;
    };
    updateDateLabel();

    labelLink.addEventListener("click", () => {
      entry.expanded = !entry.expanded;
      this.renderUI();
    });

    header.appendChild(removeBtn);
    header.appendChild(labelLink);
    panel.appendChild(header);

    const body = document.createElement("div");
    body.className = `body ${entry.expanded ? "" : "hidden"}`;

    const formEl = document.createElement("div");
    formEl.className = "date";

    const modeDiv = document.createElement("div");
    modeDiv.className = "mode";
    const modeCheck = document.createElement("input");
    modeCheck.type = "checkbox";
    modeCheck.className = "checkbox";
    modeCheck.checked = entry.excluded;
    const modeLabel = document.createElement("span");
    modeLabel.className = "recurrence-label";
    modeLabel.textContent = t("Exclude this date");
    modeCheck.addEventListener("change", () => {
      entry.excluded = modeCheck.checked;
      updateDateLabel();
      this.syncToTextarea();
    });
    modeDiv.appendChild(modeCheck);
    modeDiv.appendChild(modeLabel);

    const dateDiv = document.createElement("div");
    dateDiv.className = "date-selector";
    const dateLabel = document.createElement("span");
    dateLabel.className = "recurrence-label";
    dateLabel.textContent = `${t("Date")}:`;
    const dateInput = document.createElement("input");
    dateInput.type = "date";
    dateInput.className = "date-field";
    const dt = parseDateString(entry.isoKey);
    dateInput.value = `${pad4(dt.getUTCFullYear())}-${pad2(dt.getUTCMonth() + 1)}-${pad2(dt.getUTCDate())}`;
    dateInput.addEventListener("change", () => {
      if (dateInput.value) {
        entry.isoKey = dateInput.value + entry.isoKey.slice(10);
        updateDateLabel();
        this.syncToTextarea();
      }
    });
    dateDiv.appendChild(dateLabel);
    dateDiv.appendChild(dateInput);

    formEl.appendChild(modeDiv);
    formEl.appendChild(dateDiv);
    body.appendChild(formEl);
    panel.appendChild(body);
    return panel;
  }
}

export function registerRecurrenceWebComponent(): void {
  if (typeof customElements !== "undefined" && !customElements.get("django-recur-widget")) {
    customElements.define("django-recur-widget", DjangoRecurWidget);
  }
}
