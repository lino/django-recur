from datetime import datetime

import recurrence
from recurrence import Recurrence, Rule


def test_truthiness_with_single_rrule():
    rule = Rule(recurrence.DAILY)
    obj = Recurrence(rrules=[rule])
    assert bool(obj)


def test_truthiness_with_single_exrule():
    rule = Rule(recurrence.DAILY)
    obj = Recurrence(exrules=[rule])
    assert bool(obj)


def test_truthiness_with_single_rdate():
    obj = Recurrence(rdates=[datetime(2014, 12, 31, 0, 0, 0)])
    assert bool(obj)


def test_truthiness_with_single_exdate():
    obj = Recurrence(exdates=[datetime(2014, 12, 31, 0, 0, 0)])
    assert bool(obj)


def test_truthiness_with_dtstart():
    obj = Recurrence(dtstart=datetime(2014, 12, 31, 0, 0, 0))
    assert bool(obj)


def test_truthiness_with_dtend():
    obj = Recurrence(dtend=datetime(2014, 12, 31, 0, 0, 0))
    assert bool(obj)


def test_falsiness_with_empty_recurrence_object():
    assert not bool(Recurrence())
