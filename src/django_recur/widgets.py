"""
Modern Web Component-backed Django widgets for recurrence fields.
"""

from __future__ import annotations

import json
from typing import Any

from django import forms, urls
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils.safestring import SafeString, mark_safe
from django.views import i18n

from django_recur.rfc8984 import JSCalendarRecurrence, RecurrenceRule

_recurrence_javascript_catalog_url: str | None = None


def find_recurrence_i18n_js_catalog() -> str | None:
    """Locate the URL for Django's JavaScriptCatalog if configured for recurrence."""
    global _recurrence_javascript_catalog_url
    if _recurrence_javascript_catalog_url:
        return _recurrence_javascript_catalog_url

    if hasattr(i18n, "javascript_catalog"):
        try:
            return urls.reverse(i18n.javascript_catalog, kwargs={"packages": "recurrence"})
        except urls.NoReverseMatch:
            pass

    def check_urlpatterns(urlpatterns: Any) -> str | None:
        for pattern in urlpatterns:
            if hasattr(pattern, "url_patterns"):
                match = check_urlpatterns(pattern.url_patterns)
                if match:
                    return match
            elif (
                hasattr(i18n, "javascript_catalog")
                and getattr(pattern, "callback", None) == i18n.javascript_catalog
                and "recurrence" in getattr(pattern, "default_args", {}).get("packages", [])
            ):
                if getattr(pattern, "name", None):
                    return urls.reverse(pattern.name)
                return urls.reverse(pattern.callback)
        return None

    root_urlconf_name = getattr(settings, "ROOT_URLCONF", None)
    if not root_urlconf_name:
        return None
    try:
        root_urlconf = __import__(root_urlconf_name, {}, {}, [""])
        url = check_urlpatterns(getattr(root_urlconf, "urlpatterns", []))
    except Exception:
        return None
    _recurrence_javascript_catalog_url = url
    return url


class RecurrenceWidget(forms.Textarea):
    """
    Textarea widget progressively enhanced by the ``<django-recur-widget>``
    TypeScript Web Component.
    """

    def __init__(
        self,
        attrs: dict[str, Any] | None = None,
        output_format: str = "rfc5545",
        **kwargs: Any,
    ) -> None:
        self.js_widget_options = kwargs
        self.output_format = output_format
        defaults: dict[str, Any] = {
            "class": "recurrence-widget",
            "data-django-recur-widget": "true",
            "data-output-format": output_format,
        }
        if kwargs:
            defaults["data-widget-options"] = json.dumps(kwargs)
        if attrs is not None:
            defaults.update(attrs)
        super().__init__(defaults)

    def format_value(self, value: Any) -> str | None:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, JSCalendarRecurrence):
            if self.output_format == "rfc8984":
                return value.to_json()
            return value.to_icalendar()
        if isinstance(value, RecurrenceRule):
            if self.output_format == "rfc8984":
                return json.dumps(value.to_jscalendar())
            return JSCalendarRecurrence(recurrence_rules=[value]).to_icalendar()
        if isinstance(value, dict):
            return json.dumps(value)
        if hasattr(value, "to_jscalendar") and self.output_format == "rfc8984":
            return json.dumps(value.to_jscalendar())
        return str(value)

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> SafeString:
        textarea_html = super().render(name, value, attrs=attrs, renderer=renderer)
        return mark_safe(
            f'<django-recur-widget data-output-format="{self.output_format}">'
            f"{textarea_html}"
            f"</django-recur-widget>"
        )

    def get_media(self) -> forms.Media:
        extra = "" if getattr(settings, "DEBUG", False) else ".min"
        js = [
            f"admin/js/vendor/jquery/jquery{extra}.js",
            "admin/js/jquery.init.js",
            staticfiles_storage.url("recurrence/js/recurrence.js"),
            staticfiles_storage.url("recurrence/js/recurrence-widget.js"),
            staticfiles_storage.url("recurrence/js/recurrence-widget.init.js"),
        ]
        i18n_media = find_recurrence_i18n_js_catalog()
        if i18n_media:
            js.insert(0, i18n_media)

        return forms.Media(
            js=js,
            css={
                "all": (staticfiles_storage.url("recurrence/css/recurrence.css"),),
            },
        )

    media = property(get_media)  # type: ignore[assignment]


class JSCalendarRecurrenceWidget(RecurrenceWidget):
    """Web Component widget configured to emit RFC 8984 JSCalendar JSON."""

    def __init__(self, attrs: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(attrs=attrs, output_format="rfc8984", **kwargs)
