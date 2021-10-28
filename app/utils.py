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
        host = 'localhost'
    return f'{scheme}://{host}'.lower()


def site_email_hostname():
    from flask import current_app

    dom = current_app.config.get('SERVER_NAME', None)
    if not dom:
        dom = 'mail.example.com'
    if dom.startswith('www.'):
        dom = dom[4:]
    return dom.lower()
