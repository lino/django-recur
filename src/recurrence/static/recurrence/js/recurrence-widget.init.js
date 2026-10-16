/**
 * Auto-initializer for django-recurrence-jscalendar widgets in Django Admin
 * and dynamic formsets.
 */
(function () {
    "use strict";

    function initWidgets(root) {
        var container = root || document;
        var textareas = container.querySelectorAll(
            "textarea.recurrence-widget:not([data-dj-recurrence-initialized])"
        );
        for (var i = 0; i < textareas.length; i++) {
            var ta = textareas[i];
            if (ta.id && ta.id.indexOf("__prefix__") !== -1) {
                continue;
            }
            ta.setAttribute("data-dj-recurrence-initialized", "true");
            if (
                ta.parentElement &&
                ta.parentElement.tagName.toLowerCase() !== "dj-recurrence-widget" &&
                window.recurrence &&
                window.recurrence.widget &&
                window.recurrence.widget.Widget
            ) {
                new window.recurrence.widget.Widget(ta.id, {});
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initWidgets(document);
        });
    } else {
        initWidgets(document);
    }

    document.addEventListener("formset:added", function (event) {
        initWidgets(event.target || document);
    });
})();
