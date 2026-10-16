from datetime import datetime

import pytest
from django.utils.timezone import make_aware

import recurrence
from recurrence import choices, deserialize
from recurrence.models import Date, Recurrence, Rule


@pytest.mark.django_db
def test_recurrence_to_recurrence_object():
    limits = Recurrence.objects.create()
    Rule.objects.create(
        recurrence=limits,
        mode=choices.INCLUSION,
        freq=recurrence.WEEKLY,
    )
    obj = limits.to_recurrence_object()
    assert [r.to_text() for r in obj.rrules] == ["weekly"]
    assert obj.exrules == []
    assert obj.rdates == []
    assert obj.exdates == []


@pytest.mark.django_db
def test_recurrence_to_recurrence_object_complex():
    limits = Recurrence.objects.create(
        dtstart=datetime(2014, 1, 1, 0, 0, 0),
        dtend=datetime(2014, 12, 31, 0, 0, 0),
    )

    Rule.objects.create(
        recurrence=limits,
        mode=choices.INCLUSION,
        freq=recurrence.WEEKLY,
        until=make_aware(datetime(2014, 12, 31, 0, 0, 0)),
    )

    Rule.objects.create(
        recurrence=limits,
        mode=choices.EXCLUSION,
        freq=recurrence.MONTHLY,
        until=make_aware(datetime(2013, 12, 31, 0, 0, 0)),
    )

    Date.objects.create(
        recurrence=limits,
        mode=choices.INCLUSION,
        dt=make_aware(datetime(2012, 12, 31, 0, 0, 0)),
    )

    Date.objects.create(
        recurrence=limits,
        mode=choices.EXCLUSION,
        dt=make_aware(datetime(2011, 12, 31, 0, 0, 0)),
    )

    obj = limits.to_recurrence_object()

    assert obj.dtstart == make_aware(datetime(2014, 1, 1, 0, 0, 0))
    assert obj.dtend == make_aware(datetime(2014, 12, 31, 0, 0, 0))

    assert len(obj.rrules) == 1
    output_rule = obj.rrules[0]
    assert output_rule.freq == recurrence.WEEKLY
    assert output_rule.until == make_aware(datetime(2014, 12, 31, 0, 0, 0))

    assert len(obj.exrules) == 1
    output_rule = obj.exrules[0]
    assert output_rule.freq == recurrence.MONTHLY
    assert output_rule.until == make_aware(datetime(2013, 12, 31, 0, 0, 0))


@pytest.mark.django_db
def test_recurrence_to_recurrence_object_non_naive_sd_ed():
    limits = Recurrence.objects.create(
        dtstart=make_aware(datetime(2014, 1, 1, 0, 0, 0)),
        dtend=make_aware(datetime(2014, 12, 31, 0, 0, 0)),
    )

    obj = limits.to_recurrence_object()

    assert obj.dtstart == make_aware(datetime(2014, 1, 1, 0, 0, 0))
    assert obj.dtend == make_aware(datetime(2014, 12, 31, 0, 0, 0))


@pytest.mark.django_db
def test_create_from_recurrence_object():
    inrule = recurrence.Rule(recurrence.WEEKLY)
    exrule = recurrence.Rule(recurrence.MONTHLY)

    limits = recurrence.Recurrence(
        dtstart=datetime(2014, 1, 1, 0, 0, 0),
        dtend=datetime(2014, 2, 3, 0, 0, 0),
        rrules=[inrule],
        exrules=[exrule],
        rdates=[datetime(2014, 2, 15, 0, 0, 0)],
        exdates=[make_aware(datetime(2014, 11, 29, 0, 0, 0))],
    )

    obj = Recurrence.objects.create_from_recurrence_object(limits)

    assert obj.dtstart == make_aware(datetime(2014, 1, 1, 0, 0, 0))
    assert obj.dtend == make_aware(datetime(2014, 2, 3, 0, 0, 0))

    rules = obj.rules.all()
    assert len(rules) == 2

    in_rules = [r for r in rules if r.mode == choices.INCLUSION]
    out_rules = [r for r in rules if r.mode == choices.EXCLUSION]

    assert len(in_rules) == 1
    assert len(out_rules) == 1

    assert in_rules[0].freq == recurrence.WEEKLY
    assert out_rules[0].freq == recurrence.MONTHLY

    dates = obj.dates.all()
    assert len(dates) == 2

    in_dates = [d for d in dates if d.mode == choices.INCLUSION]
    out_dates = [d for d in dates if d.mode == choices.EXCLUSION]

    assert len(in_dates) == 1
    assert len(out_dates) == 1

    assert in_dates[0].dt == make_aware(datetime(2014, 2, 15, 0, 0, 0))
    assert out_dates[0].dt == make_aware(datetime(2014, 11, 29, 0, 0, 0))


@pytest.mark.django_db
def test_deserialize_to_recurrence_regression():
    obj = deserialize("DTSTART:20201015T000000\nRRULE:FREQ=WEEKLY;COUNT=30;INTERVAL=1;WKST=MO")
    Recurrence.objects.create_from_recurrence_object(obj)
