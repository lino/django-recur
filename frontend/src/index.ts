/**
 * Main entrypoint for the django-recurrence-jscalendar Web Component bundle.
 */

export * from "./codec";
export * from "./legacy-bridge";
export * from "./types";
export * from "./widget-element";

import { installLegacyRecurrenceNamespace, setupDomObserver } from "./legacy-bridge";
import { registerRecurrenceWebComponent } from "./widget-element";

registerRecurrenceWebComponent();
installLegacyRecurrenceNamespace();
setupDomObserver();
