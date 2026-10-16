from datetime import datetime

import recurrence
from recurrence import Recurrence, Rule

RULE = Rule(recurrence.DAILY)

PATTERN = Recurrence(
    dtstart=datetime(2014, 1, 2, 0, 0, 0),
    dtend=datetime(2014, 1, 3, 0, 0, 0),
    rrules=[RULE],
)


def test_occurrences_with_implicit_start_and_end():
    occurrences = list(PATTERN.occurrences())

    assert occurrences == [
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
    ]

    assert PATTERN.count() == 2


def test_occurrences_with_explicit_start():
    occurrences = list(
        PATTERN.occurrences(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
    ]

    assert (
        PATTERN.count(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
        )
        == 3
    )


def test_occurrences_with_explicit_end():
    occurrences = list(
        PATTERN.occurrences(
            dtend=datetime(2014, 1, 4, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
    ]

    assert (
        PATTERN.count(
            dtend=datetime(2014, 1, 4, 0, 0, 0),
        )
        == 3
    )


def test_occurrences_with_explicit_start_and_end():
    occurrences = list(
        PATTERN.occurrences(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 4, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
    ]

    assert (
        PATTERN.count(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 4, 0, 0, 0),
        )
        == 4
    )


def test_occurrences_with_specific_include_dates():
    pattern = Recurrence(
        rdates=[
            datetime(2014, 1, 1, 0, 0, 0),
            datetime(2014, 1, 2, 0, 0, 0),
        ]
    )

    occurrences = list(
        pattern.occurrences(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 4, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 4, 0, 0, 0),
    ]

    assert (
        pattern.count(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 4, 0, 0, 0),
        )
        == 3
    )

    all_occurrences = list(pattern.occurrences())

    assert all_occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
        datetime(2014, 1, 2, 0, 0, 0),
    ]

    assert pattern.count() == 2


def test_occurrences_until():
    rule = Rule(recurrence.DAILY, until=datetime(2014, 1, 3, 0, 0, 0))

    pattern = Recurrence(rrules=[rule])

    occurrences = list(
        pattern.occurrences(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 5, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
        datetime(2014, 1, 2, 0, 0, 0),
        datetime(2014, 1, 3, 0, 0, 0),
        datetime(2014, 1, 5, 0, 0, 0),
    ]

    assert (
        pattern.count(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 5, 0, 0, 0),
        )
        == 4
    )

    occurrences = list(
        pattern.occurrences(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 2, 0, 0, 0),
        )
    )

    assert occurrences == [
        datetime(2014, 1, 1, 0, 0, 0),
        datetime(2014, 1, 2, 0, 0, 0),
    ]

    assert (
        pattern.count(
            dtstart=datetime(2014, 1, 1, 0, 0, 0),
            dtend=datetime(2014, 1, 2, 0, 0, 0),
        )
        == 2
    )


def test_before():
    assert PATTERN.before(datetime(2014, 1, 3, 0, 0, 0)) == datetime(2014, 1, 2, 0, 0, 0)

    assert PATTERN.before(datetime(2014, 1, 3, 0, 0, 0), inc=True) == datetime(2014, 1, 3, 0, 0, 0)


def test_after():
    assert PATTERN.after(datetime(2014, 1, 2, 0, 0, 0)) == datetime(2014, 1, 3, 0, 0, 0)

    assert PATTERN.after(datetime(2014, 1, 2, 0, 0, 0), inc=True) == datetime(2014, 1, 2, 0, 0, 0)
