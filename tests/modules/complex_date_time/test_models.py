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
    assert cdt.datetime == cdt.get_datetime_timezone()

    with db.session.begin():
        db.session.add(cdt)
    assert cdt.guid
    test = ComplexDateTime.query.get(cdt.guid)
    assert test
    assert test.datetime == cdt.datetime
    assert test.isoformat_timezone() == cdt.isoformat_timezone()

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
    assert cdt.get_datetime_timezone().year == 2021
    assert cdt.get_datetime_timezone().month == 1
    assert cdt.get_datetime_timezone().day == 1
    # and time should be midnight of (in timezone-based version)
    assert 'T00:00:00' in cdt.isoformat_timezone()
    # but we are only this specific:
    assert cdt.specificity == Specificities.year

    # another quicky check of day-level specificity
    cdt = ComplexDateTime.from_list([1999, 5, 31], 'US/Eastern')
    assert cdt
    assert cdt.get_datetime_timezone().year == 1999
    assert cdt.get_datetime_timezone().month == 5
    assert cdt.get_datetime_timezone().day == 31
    assert 'T00:00:00' in cdt.isoformat_timezone()
    assert cdt.specificity == Specificities.day
