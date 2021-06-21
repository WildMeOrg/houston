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
        log_message = kwargs.get('log_message', '')
        self.message = kwargs.get('message', log_message)
        self.status_code = kwargs.get('status_code', 400)

        # Allow other params to be passed in exception
        self._kwargs = kwargs
        if log_message == '' and self.message != '':
            log_message = self.message

        log.warning(f'Failed: {log_message} {self.status_code}')
        # TODO This is where Audit Logging will hook into the system.

    def get_val(self, argval, default):
        return self._kwargs.get(argval, default)
