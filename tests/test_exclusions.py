from datetime import datetime

import recurrence
from recurrence import Recurrence, Rule


def test_exclusion_date():
    rule = Rule(recurrence.DAILY)

    pattern = Recurrence(
        dtstart=datetime(2014, 1, 2, 0, 0, 0),
        dtend=datetime(2014, 1, 4, 0, 0, 0),
        rrules=[rule],
        exdates=[datetime(2014, 1, 3, 0, 0, 0)],
    )

    occurrences = list(pattern.occurrences())

    assert occurrences == [
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
    ]

    assert pattern.count() == 2


def test_exclusion_date_no_limits():
    pattern = Recurrence(
        rdates=[
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 2, 0, 0, 0),
        ],
        exdates=[datetime(2014, 1, 2, 0, 0, 0)],
    )

    occurrences = list(pattern.occurrences())

    assert occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
    ]

    assert pattern.count() == 1


def test_exclusion_rule():
    inclusion_rule = Rule(recurrence.DAILY)

    exclusion_rule = Rule(recurrence.WEEKLY, byday=recurrence.THURSDAY)

    pattern = Recurrence(
        dtstart=datetime(2014, 1, 2, 0, 0, 0),
        dtend=datetime(2014, 1, 4, 0, 0, 0),
        rrules=[inclusion_rule],
        exrules=[exclusion_rule],
    )

    occurrences = list(pattern.occurrences())

    assert occurrences == [
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
    ]

    assert pattern.count() == 2
