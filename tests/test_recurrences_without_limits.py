from datetime import datetime

import recurrence
from recurrence import Recurrence, Rule

RULE = Rule(recurrence.DAILY)

PATTERN = Recurrence(rrules=[RULE])


def test_between_without_dtend_and_dtstart():
    occurrences = list(
        PATTERN.between(
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 4, 0, 0, 0),
        )
    )

    assert occurrences == []


def test_between_with_dtend_and_dtstart_dtend_lower_than_end():
    occurrences = list(
        PATTERN.between(
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 6, 0, 0, 0),
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 4, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
    ]


def test_between_with_dtend_and_dtstart_dtend_higher_than_end():
    occurrences = list(
        PATTERN.between(
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 6, 0, 0, 0),
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 8, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
        datetime(2014, 1, 5, 0, 0, 0),
    ]


def test_between_with_dtend_and_dtstart_limits_equal_exclusive():
    occurrences = list(
        PATTERN.between(
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 6, 0, 0, 0),
            dtstart=datetime(2014, 1, 2, 0, 0, 0),
            dtend=datetime(2014, 1, 6, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
        datetime(2014, 1, 5, 0, 0, 0),
    ]


def test_between_with_dtend_and_dtstart_limits_equal_inclusive():
    occurrences = list(
        PATTERN.between(
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 6, 0, 0, 0),
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 6, 0, 0, 0),
            inc=True,
        )
    )

    assert occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
        datetime(2014, 1, 5, 0, 0, 0),
        datetime(2014, 1, 6, 0, 0, 0),
    ]


def test_between_with_dtend_and_dtstart_dtstart_lower_than_start():
    occurrences = list(
        PATTERN.between(
            datetime(2014, 1, 2, 0, 0, 0),
            datetime(2014, 1, 6, 0, 0, 0),
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 6, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
        datetime(2014, 1, 5, 0, 0, 0),
    ]


def test_between_with_dtend_and_dtstart_dtstart_higher_than_start():
    occurrences = list(
        PATTERN.between(
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 6, 0, 0, 0),
            dtstart=datetime(2014, 1, 2, 0, 0, 0),
            dtend=datetime(2014, 1, 6, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
        datetime(2014, 1, 5, 0, 0, 0),
    ]
