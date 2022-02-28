# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
Houston Common utils
--------------------------
"""

from flask_login import current_user  # NOQA
import app.extensions.logging as AuditLog  # NOQA


class HoustonException(Exception):
    def __init__(
        self, logger, log_message, fault=AuditLog.AuditType.FrontEndFault, **kwargs
    ):
        self.message = kwargs.get('message', log_message)
        self.status_code = kwargs.get('status_code', 400)

        # Allow other params to be passed in exception
        self._kwargs = kwargs
        if log_message == '' and self.message != '':
            log_message = self.message

        AuditLog.audit_log(logger, f'Failed: {log_message} {self.status_code}', fault)

    def __str__(self):
        return self.message

    def get_val(self, argval, default):
        return self._kwargs.get(argval, default)


# h/t https://www.delftstack.com/howto/python/python-unicode-to-string/
def to_ascii(val):
    if val is None or not isinstance(val, str):
        return None
    import unicodedata

    return unicodedata.normalize('NFKD', val).encode('ascii', 'ignore').decode()


# generally speaking, we should use flask url_for() method to construct urls, i guess.  but this seems handy to have?
#   see:   https://flask.palletsprojects.com/en/2.0.x/quickstart/#url-building
#   and:   https://flask.palletsprojects.com/en/2.0.x/api/#flask.url_for
def site_url_prefix():
    from flask import current_app

    scheme = current_app.config.get('PREFERRED_URL_SCHEME', 'https')
    host = current_app.config.get('SERVER_NAME', 'codex.example.com')
    if not scheme or not host:
        scheme = 'http'
        host = 'localhost:84'  # development
    return f'{scheme}://{host}'.lower()


def site_email_hostname():
    from flask import current_app

    dom = current_app.config.get('SERVER_NAME', None)
    if not dom:
        dom = 'mail.example.com'
    if dom.startswith('www.'):
        dom = dom[4:]
    return dom.lower()


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
    from flask import current_app
    from celery.result import AsyncResult

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
    from datetime import datetime

    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f'no time zone provided in {iso}')
    return dt


# this "should" handle cases such as: tzstring='+07:00', '-0400', 'US/Pacific'
def datetime_as_timezone(dt, tzstring):
    from dateutil import tz
    from datetime import datetime

    if not dt or not isinstance(dt, datetime):
        raise ValueError('must pass datetime object')
    zone = tz.gettz(tzstring)
    if not zone:
        raise ValueError(f'unknown time zone value "{tzstring}"')
    return dt.astimezone(zone)


# in a nutshell dt.tzname() *sucks*.  i am not sure what it is showing, but its bunk.
#   this is an attempt to get a string *that can be read back in above*
def normalized_timezone_string(dt):
    from datetime import datetime

    if not dt or not isinstance(dt, datetime):
        raise ValueError('must pass datetime object')
    return dt.strftime('UTC%z')
