from django.conf import settings
from django.test import TestCase, override_settings

from recurrence import settings as r_settings


class TestTimezoneSettings(TestCase):
    @override_settings(RECURRENCE_USE_TZ=True, USE_TZ=False)
    def test_recurrence_tz_true(self):
        assert r_settings.deserialize_tz()

    @override_settings(RECURRENCE_USE_TZ=False, USE_TZ=True)
    def test_recurrence_tz_false(self):
        assert not r_settings.deserialize_tz()

    @override_settings(USE_TZ=True)
    def test_fallback_to_use_tz_true(self):
        del settings.RECURRENCE_USE_TZ
        assert r_settings.deserialize_tz()

    @override_settings(USE_TZ=False)
    def test_fallback_to_use_tz_false(self):
        del settings.RECURRENCE_USE_TZ
        assert not r_settings.deserialize_tz()
