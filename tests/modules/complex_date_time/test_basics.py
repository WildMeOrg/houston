# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import datetime

import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('complex_date_time'), reason='ComplexDateTime module disabled'
)
def test_models(db, request):
    from dateutil import tz

    from app.modules.complex_date_time.models import ComplexDateTime, Specificities

    try:
        cdt = ComplexDateTime('test', 'test', 'test')
    except ValueError as ve:
        assert 'must pass a datetime object' == str(ve)

    dt = datetime.datetime.utcnow()
    try:
        cdt = ComplexDateTime(dt, None, None)
    except ValueError as ve:
        assert 'must provide a time zone' == str(ve)

    try:
        cdt = ComplexDateTime(dt, 'fubar', None)
    except ValueError as ve:
        assert 'unrecognized time zone' in str(ve)

    try:
        cdt = ComplexDateTime(dt, 'US/Pacific', None)
    except ValueError as ve:
        assert 'invalid specificity' in str(ve)

    # this should finally work!
    cdt = ComplexDateTime(dt, 'US/Pacific', Specificities.day)
    assert cdt
    assert cdt.datetime == dt.astimezone(tz.UTC)
    assert cdt.datetime == cdt.get_datetime_in_timezone()
    assert cdt.lower_bound < cdt.datetime
    assert cdt.upper_bound > cdt.datetime
    assert (
        cdt.sort_value
        == (
            datetime.datetime.timestamp(cdt.upper_bound)
            + datetime.datetime.timestamp(cdt.lower_bound)
        )
        / 2
    )

    with db.session.begin():
        db.session.add(cdt)
    assert cdt.guid
    test = ComplexDateTime.query.get(cdt.guid)
    assert test
    assert test.datetime == cdt.datetime
    assert test.isoformat_in_timezone() == cdt.isoformat_in_timezone()

    dtdata = []  # invalid
    try:
        cdt = ComplexDateTime.from_data(dtdata)
    except ValueError as ve:
        assert str(ve) == 'No data passed in'

    dtdata = {'time': []}  # also invalid
    try:
        cdt = ComplexDateTime.from_data(dtdata)
    except ValueError as ve:
        assert str(ve) == 'time field must be a string'

    dtdata = {
        'time': '1999-01-01T00:01:02+01:00',
    }
    try:
        cdt = ComplexDateTime.from_data(dtdata)
    except ValueError as ve:
        assert str(ve) == 'timeSpecificity field missing'

    dtdata = {
        'time': '1999-01-01T00:01:02+01:00',
        'timeSpecificity': 'fubar',
    }
    try:
        cdt = ComplexDateTime.from_data(dtdata)
    except ValueError as ve:
        assert str(ve) == 'timeSpecificity fubar not supported'

    # Now a valid day one
    dtdata = {
        'time': '1999-05-31T00:01:02+01:00',
        'timeSpecificity': 'day',
    }
    cdt = ComplexDateTime.from_data(dtdata)

    # now some comparisons.  note this assumes we have not traveled back in time prior to 1999.
    dt_later = datetime.datetime.utcnow()
    # same specificity as cdt
    later = ComplexDateTime(dt_later, 'US/Pacific', Specificities.day)
    later_mountain = ComplexDateTime(dt_later, 'US/Mountain', Specificities.day)
    later_mountain2 = ComplexDateTime(dt_later, 'US/Mountain', Specificities.day)
    # different specificity, so cant do > or < comparisons
    later_month = ComplexDateTime(dt_later, 'US/Pacific', Specificities.month)

    assert cdt != later
    # specificities match, so these work:
    assert cdt < later
    assert later >= cdt

    # note that timezone is irrelevant for these comparisons, as utc value is used
    assert later == later_mountain
    # but is_identical takes into account all attributes
    assert not later.is_identical(later_mountain)
    assert later_mountain.is_identical(later_mountain2)
    assert not later_month.is_identical(later_mountain)

    # this are fine because == and != dont care about specificity-compatibility
    assert not cdt == later_month
    assert cdt != later_month
    # but the others need equivalent specificities so give us NotImplementedErrors
    try:
        cdt > later_month
    except NotImplementedError as nie:
        assert 'mismatched specificities' in str(nie)
    try:
        cdt <= later_month
    except NotImplementedError as nie:
        assert 'mismatched specificities' in str(nie)


@pytest.mark.skipif(
    module_unavailable('complex_date_time'), reason='ComplexDateTime module disabled'
)
def test_nlp_time():
    from app.modules.complex_date_time.models import Specificities
    from app.utils import nlp_parse_complex_date_time

    refdate = '2019-08-15'
    text = 'a week ago at 3:30'
    try:
        cdt = nlp_parse_complex_date_time(
            text, reference_date=refdate, timezone='US/Mountain'
        )
    except RuntimeError:
        pytest.skip('NLP jar files not available')
    assert cdt
    assert cdt.isoformat_in_timezone() == '2019-08-07T21:30:00-06:00'
    assert cdt.specificity == Specificities.time

    text = 'last month'
    cdt = nlp_parse_complex_date_time(text, reference_date=refdate)
    assert cdt
    assert cdt.isoformat_in_timezone() == '2019-07-01T00:00:00+00:00'
    assert cdt.specificity == Specificities.month

    # some of the nasty range-y stuff
    text = 'during last winter'
    cdt = nlp_parse_complex_date_time(text, reference_date=refdate)
    assert cdt
    assert cdt.isoformat_in_timezone() == '2018-01-01T00:00:00+00:00'
    assert cdt.specificity == Specificities.month

    text = 'yesterday morning'
    cdt = nlp_parse_complex_date_time(text, reference_date=refdate)
    assert cdt
    assert cdt.isoformat_in_timezone() == '2019-08-14T09:00:00+00:00'
    assert cdt.specificity == Specificities.time

    cdt = nlp_parse_complex_date_time('i have no idea')
    assert not cdt

    cdt = nlp_parse_complex_date_time('2021', reference_date='fubar')
    assert not cdt

    # this should work
    cdt = nlp_parse_complex_date_time(
        '2021', reference_date=refdate, timezone='US/Pacific'
    )
    assert cdt

    # since only year passed, should be set to January 1
    assert cdt.get_datetime_in_timezone().year == 2021
    assert cdt.get_datetime_in_timezone().month == 1
    assert cdt.get_datetime_in_timezone().day == 1
    # and time should be midnight of (in timezone-based version)
    assert 'T00:00:00' in cdt.isoformat_in_timezone()
    # but we are only this specific:
    assert cdt.specificity == Specificities.year

    # another quicky check of day-level specificity
    cdt = nlp_parse_complex_date_time(
        '1999:05:31', reference_date=refdate, timezone='US/Eastern'
    )
    assert cdt
    assert cdt.get_datetime_in_timezone().year == 1999
    assert cdt.get_datetime_in_timezone().month == 5
    assert cdt.get_datetime_in_timezone().day == 31
    assert 'T00:00:00' in cdt.isoformat_in_timezone()
    assert cdt.specificity == Specificities.day


@pytest.mark.skipif(
    module_unavailable('complex_date_time'), reason='ComplexDateTime module disabled'
)
def test_nlp_time_mocked():
    from unittest.mock import patch

    import sutime

    from app.utils import nlp_parse_complex_date_time

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return []

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('')
        assert not cdt

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [{}]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('')
        assert not cdt

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'DATE',
                    'value': '2022-SP',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('was spring')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-03-01T00:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'DATE',
                    'value': '2022-SU',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('in summer')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-06-01T00:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'DATE',
                    'value': '2022-FA',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('fall')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-09-01T00:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'DATE',
                    'value': '2022-WI',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('winter time brr')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-01-01T00:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'DATE',
                    'value': '0-0-0',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('gives warning, no result')
        assert not cdt

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'TIME',
                    'value': '2022-01-02TMO',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('morning')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-01-02T09:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'TIME',
                    'value': '2022-01-02TAF',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('afternoon')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-01-02T13:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'TIME',
                    'value': '2022-01-02TEV',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('evening')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-01-02T17:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'TIME',
                    'value': '2022-01-02TNI',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('night time')
        assert cdt
        assert cdt.isoformat_in_timezone() == '2022-01-02T22:00:00+00:00'

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'TIME',
                    'value': 'broken',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('broken')
        assert not cdt

    class mock_SUTime(object):
        def parse(self, val, reference_date=None):
            return [
                {
                    'type': 'UNKNOWN',
                    'value': 'broken',
                }
            ]

    mock_sutime = mock_SUTime()
    with patch.object(sutime, 'SUTime', return_value=mock_sutime):
        cdt = nlp_parse_complex_date_time('broken')
        assert not cdt
