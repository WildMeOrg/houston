# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
Houston Common utils
--------------------------
"""
import logging

from flask_login import current_user  # NOQA

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class HoustonException(Exception):
    def __init__(self, **kwargs):
        log_message = kwargs['log_message'] if 'log_message' in kwargs else ''
        self.message = kwargs['message'] if 'message' in kwargs else log_message
        self.status_code = kwargs['status_code'] if 'status_code' in kwargs else 400

        # Allow other params to be passed in exception
        self._kwargs = dict(kwargs)

        log.warning(f'Failed: {log_message} {self.status_code}')
        # TODO This is where Audit Logging will hook into the system.

    def get_string_val(self, argval):
        return self._kwargs[argval] if argval in self._kwargs else ''

    def get_int_val(self, argval):
        return self._kwargs[argval] if argval in self._kwargs else 0
