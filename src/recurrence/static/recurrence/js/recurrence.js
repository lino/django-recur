/**
 * django-recur legacy namespace bootstrap.
 * The full implementation and <django-recur-widget> Web Component are bundled
 * into recurrence-widget.js from the TypeScript pipeline in frontend/.
 */
(function (global) {
    "use strict";
    global.recurrence = global.recurrence || {
        YEARLY: 0,
        MONTHLY: 1,
        WEEKLY: 2,
        DAILY: 3,
        HOURLY: 4,
        MINUTELY: 5,
        SECONDLY: 6,
        INCLUSION: true,
        EXCLUSION: false,
         SUNDAY: 6,
        MONDAY: 0,
        TUESDAY: 1,
        WEDNESDAY: 2,
        THURSDAY: 3,
        FRIDAY: 4,
        SATURDAY: 5
    };
})(typeof window !== "undefined" ? window : globalThis);
