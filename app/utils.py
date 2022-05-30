# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
Houston Common utils
--------------------------
"""

import datetime
import logging

from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog  # NOQA

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class HoustonException(Exception):
    def __init__(
        self,
        logger,
        log_message,
        fault=AuditLog.AuditType.FrontEndFault,
        obj=None,
        **kwargs,
    ):
        self.message = kwargs.get('message', log_message)
        self.status_code = kwargs.get('status_code', 400)

        # Allow other params to be passed in exception
        self._kwargs = kwargs
        if log_message == '' and self.message != '':
            log_message = self.message

        if obj:
            AuditLog.audit_log_object(
                logger, obj, f'Failed: {log_message} {self.status_code}', fault
            )
        else:
            AuditLog.audit_log(logger, f'Failed: {log_message} {self.status_code}', fault)

    def __str__(self):
        # something, somewhere was setting this as a tuple, hence this possibly redudant str()
        return str(self.message)

    def get_val(self, argval, default):
        return self._kwargs.get(argval, default)


# h/t https://www.delftstack.com/howto/python/python-unicode-to-string/
def to_ascii(val):
    if val is None or not isinstance(val, str):
        return None
    import unicodedata

    return unicodedata.normalize('NFKD', val).encode('ascii', 'ignore').decode()


# optionally filter on type
def get_celery_tasks_scheduled(type=None):
    from flask import current_app

    inspect = current_app.celery.control.inspect()
    workers = inspect.ping()
    if not workers:
        raise NotImplementedError('there are no celery workers to get data from')
    scheduled = inspect.scheduled()
    if not scheduled:
        return []
    tasks = []
    for queue, items in scheduled.items():
        for item in items:
            if type and 'request' in item and item['request'].get('type') != type:
                continue
            tasks.append(item)
    return tasks


def get_celery_data(task_id):
    from celery.result import AsyncResult
    from flask import current_app

    inspect = current_app.celery.control.inspect()
    workers = inspect.ping()
    if not workers:
        raise NotImplementedError('there are no celery workers to get data from')
    # first we check to see if task is marked as revoked; and ignore if so
    revoked = inspect.revoked()
    if revoked:
        for tids in revoked.values():
            for tid in tids:
                if tid == task_id:
                    return None, {'revoked': True}
    # note: scheduled() does seem to empty when tasks are run, but revoked() stick around even after their eta
    scheduled = inspect.scheduled()
    if scheduled:
        for queue, items in scheduled.items():
            for item in items:
                if 'request' in item and item['request'].get('id') == task_id:
                    return AsyncResult(task_id), item
    return None, None


# will throw ValueError if cant parse string
#  also *requires* timezone on iso string or will ValueError
def iso8601_to_datetime_with_timezone(iso):
    dt = datetime.datetime.fromisoformat(iso)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f'no time zone provided in {iso}')
    return dt


# this "should" handle cases such as: tzstring='+07:00', '-0400', 'US/Pacific'
def datetime_as_timezone(dt, tzstring):
    from dateutil import tz

    if not dt or not isinstance(dt, datetime.datetime):
        raise ValueError('must pass datetime object')
    zone = tz.gettz(tzstring)
    if not zone:
        raise ValueError(f'unknown time zone value "{tzstring}"')
    return dt.astimezone(zone)


# in a nutshell dt.tzname() *sucks*.  i am not sure what it is showing, but its bunk.
#   this is an attempt to get a string *that can be read back in above*
def normalized_timezone_string(dt):
    if not dt or not isinstance(dt, datetime.datetime):
        raise ValueError('must pass datetime object')
    return dt.strftime('UTC%z')


# converts string like 'Wed, 25 May 2022 00:16:42 GMT' which is what datetime is stringified as
def datetime_string_to_isoformat(dts):
    import re
    from datetime import datetime

    if not isinstance(dts, str):
        return None

    # if are already in isoformat, just return
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', dts):
        return dts

    try:
        d = datetime.strptime(dts, '%a, %d %b %Y %H:%M:%S %Z')
    except ValueError as err:
        log.warning(f'could not convert {dts}: {str(err)}')
        return None
    return d.isoformat() + 'Z'


# As some filenames are problematic, may contain special chars ";&/." etc store all filenames as a hash of the
# original filename but maintain the extension
def get_stored_filename(input_filename):
    import hashlib

    if input_filename is None:
        return None

    return f'{hashlib.sha256(input_filename.encode()).hexdigest()}'


def nlp_parse_complex_date_time(
    text, reference_date=None, tz='UTC', time_specificity=None
):
    from sutime import SUTime

    from app.modules.complex_date_time.models import ComplexDateTime, Specificities

    # https://github.com/FraBle/python-sutime
    # will throw RuntimeError if jars are not there
    #  TODO readme on how to actually install requirements here (and/or automate)
    sut = SUTime(mark_time_ranges=True, include_range=True)

    # this will be an array [start,end] if found, or just [start]
    #   but we only use start value
    results = sut.parse(text, reference_date=reference_date)

    if not results:
        return None

    # iterate over results until we get something we can use
    for res in results:
        value = res.get('value')
        if not value:
            continue

        if res.get('type') == 'DATE':
            # handle seasons
            if value[5:] == 'SP':
                value = value[:5] + '03'
            elif value[5:] == 'SU':
                value = value[:5] + '06'
            elif value[5:] == 'FA':
                value = value[:5] + '09'
            elif value[5:] == 'WI':
                # winter is weird - is it this year or next ... or last?
                value = value[:5] + '01'
            parts = [int(p) for p in value.split('-')]
            try:
                return ComplexDateTime.from_list(parts, tz, time_specificity)
            except Exception as ex:
                log.warning(
                    f'nlp_parse_complex_date_time(): DATE exception on value={value} [from {res}]: {str(ex)}'
                )

        elif res.get('type') == 'TIME':
            # handle parts of day
            if value[-3:] == 'TMO':
                value = value[:11] + '09:00'
            elif value[-3:] == 'TAF':
                value = value[:11] + '13:00'
            elif value[-3:] == 'TEV':
                value = value[:11] + '17:00'
            elif value[-3:] == 'TNI':
                value = value[:11] + '22:00'
            try:
                return ComplexDateTime.from_data(
                    {
                        'time': {
                            'datetime': value,
                            'timezone': tz,
                            'specificity': Specificities.time,
                        }
                    }
                )
            except Exception as ex:
                log.warning(
                    f'nlp_parse_complex_date_time(): TIME exception on value={value} [from {res}]: {str(ex)}'
                )

        else:
            log.warning(f'nlp_parse_complex_date_time(): unknown type in {res}')

    return None


# match is a string, and candidates can be one of:
#   * list (of text strings)
#   * dict with { id0: text0, id1: text1, ... }
# this will return a list (ordered by best match to worst) of how well match fuzzy-matched the candidates.
#   the list contains dicts like: { id: xxx, text: yyy, score: zzz } (id will be omitted if only a list is passed in)
def fuzzy_match(match, candidates):
    from fuzzywuzzy import fuzz

    lmatch = match.lower()
    if isinstance(candidates, list):
        res = [{'text': i.lower()} for i in candidates]
    else:
        res = [{'id': i, 'text': candidates[i].lower()} for i in candidates]
    for c in res:
        c['score'] = fuzz.partial_ratio(lmatch, c['text']) + fuzz.ratio(lmatch, c['text'])
    return sorted(res, key=lambda d: -d['score'])


def get_redis_connection():
    import redis
    from flask import current_app

    # this is cribbed from tus usage of redis - i guess its trying to reycle
    #   a previous connection rather than always reconnecting.  ymmv?
    #
    # Find the stack on which we want to store the database connection.
    # Starting with Flask 0.9, the _app_ctx_stack is the correct one,
    # before that we need to use the _request_ctx_stack.
    try:
        from flask import _app_ctx_stack as stack
    except ImportError:  # pragma: no cover
        from flask import _request_ctx_stack as stack

    redis_connection_string = current_app.config['REDIS_CONNECTION_STRING']
    if not redis_connection_string:
        raise ValueError('missing REDIS_CONNECTION_STRING')
    ctx = stack.top
    if not ctx:
        raise ValueError('could not get ctx')
    if not hasattr(ctx, 'codex_persisted_values_redis'):
        ctx.codex_persisted_values_redis = redis.from_url(redis_connection_string)
    conn = ctx.codex_persisted_values_redis
    if not conn:
        raise ValueError('unable to obtain redis connection')
    return conn


def set_persisted_value(key, value):
    conn = get_redis_connection()
    return conn.set(key, value)


def get_persisted_value(key):
    conn = get_redis_connection()
    val = conn.get(key)
    return val.decode('utf-8') if val else None


def sizeof(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return f'{num:3.1f}{unit}{suffix}'
        num /= 1024.0
    return f'{num:.1f}Yi {suffix}'
