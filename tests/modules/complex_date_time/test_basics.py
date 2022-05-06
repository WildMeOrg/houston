# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import pytest
from tests.utils import module_unavailable
from app.utils import (
    iso8601_to_datetime_with_timezone,
    datetime_as_timezone,
    normalized_timezone_string,
)
from datetime import datetime


@pytest.mark.skipif(
    module_unavailable('complex_date_time'), reason='ComplexDateTime module disabled'
)
def test_utils():
    iso = '2021-12-01T00:00:01'
    try:
        dt = iso8601_to_datetime_with_timezone(iso)
    except ValueError as ve:
        assert 'no time zone provided' in str(ve)

    iso = '2021-12-01T12:00:00-07:00'
    dt = iso8601_to_datetime_with_timezone(iso)
    assert dt
    assert dt.tzinfo
    assert dt.tzname() == 'UTC-07:00'

    shifted = datetime_as_timezone(dt, 'UTC-04:00')
    assert shifted
    assert normalized_timezone_string(shifted) == 'UTC-0400'
    assert shifted == dt

    try:
        shifted = datetime_as_timezone(dt, 'fubar')
    except ValueError as ve:
        assert 'unknown time zone' in str(ve)


@pytest.mark.skipif(
    module_unavailable('complex_date_time'), reason='ComplexDateTime module disabled'
)
def test_models(db, request):
    from app.modules.complex_date_time.models import ComplexDateTime, Specificities
    from dateutil import tz

    try:
        cdt = ComplexDateTime('test', 'test', 'test')
    except ValueError as ve:
        assert 'must pass a datetime object' == str(ve)

    dt = datetime.utcnow()
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
        assert str(ve).startswith('invalid data: ')

    dtdata = {'time': []}  # also invalid
    try:
        cdt = ComplexDateTime.from_data(dtdata)
    except ValueError as ve:
        assert str(ve).startswith('invalid data: ')

    dtdata = {
        'time': '1999-01-01T00:01:02+01:00',
    }
    try:
        cdt = ComplexDateTime.from_data(dtdata)
    except ValueError as ve:
        assert 'invalid specificity' in str(ve)

    dtdata = {
        'time': '1999-01-01T00:01:02+01:00',
        'timeSpecificity': 'fubar',
    }
    try:
        cdt = ComplexDateTime.from_data(dtdata)
    except ValueError as ve:
        assert 'invalid specificity' in str(ve)

    dtdict = []  # invalid
    try:
        cdt = ComplexDateTime.from_dict(dtdict)
    except ValueError as ve:
        assert 'invalid data' in str(ve)

    dtdict = {
        'components': 'fubar',
    }
    try:
        cdt = ComplexDateTime.from_dict(dtdict)
    except ValueError as ve:
        assert 'components must be a list' in str(ve)

    dtdict = {
        'fubar': 1,
    }
    try:
        cdt = ComplexDateTime.from_dict(dtdict)
    except ValueError as ve:
        assert 'missing datetime value' in str(ve)

    dtdict = {
        'datetime': '2000-02-02T02:02:02',  # no tz
    }
    try:
        cdt = ComplexDateTime.from_dict(dtdict)
    except ValueError as ve:
        assert 'timezone not passed' in str(ve)

    dtdict = {
        'datetime': '2000-02-02T02:02:02+03:00',
        'specificity': 'fail',
    }
    try:
        cdt = ComplexDateTime.from_dict(dtdict)
    except ValueError as ve:
        assert 'invalid specificity' in str(ve)

    dtlist = None
    try:
        cdt = ComplexDateTime.from_list(dtlist, 'fubar')
    except ValueError as ve:
        assert 'must pass list' in str(ve)

    dtlist = [2021]
    try:
        cdt = ComplexDateTime.from_list(dtlist, 'fubar')
    except ValueError as ve:
        assert 'unrecognized time zone' in str(ve)

    # this should work
    cdt = ComplexDateTime.from_list(dtlist, 'US/Pacific')
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
    cdt = ComplexDateTime.from_list([1999, 5, 31], 'US/Eastern')
    assert cdt
    assert cdt.get_datetime_in_timezone().year == 1999
    assert cdt.get_datetime_in_timezone().month == 5
    assert cdt.get_datetime_in_timezone().day == 31
    assert 'T00:00:00' in cdt.isoformat_in_timezone()
    assert cdt.specificity == Specificities.day

    # now some comparisons.  note this assumes we have not traveled back in time prior to 1999.
    dt_later = datetime.utcnow()
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
    from app.utils import nlp_parse_complex_date_time
    from app.modules.complex_date_time.models import Specificities

    refdate = '2019-08-15'
    text = 'a week ago at 3:30'
    try:
        cdt = nlp_parse_complex_date_time(text, reference_date=refdate, tz='US/Mountain')
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
