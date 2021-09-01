# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
Houston Common utils
--------------------------
"""

from flask_login import current_user  # NOQA
from app.extensions.logging import audit_log, AuditType


class HoustonException(Exception):
    def __init__(self, logger, log_message, **kwargs):
        self.message = kwargs.get('message', log_message)
        self.status_code = kwargs.get('status_code', 400)

        # Allow other params to be passed in exception
        self._kwargs = kwargs
        if log_message == '' and self.message != '':
            log_message = self.message

        logger.warning(f'Failed: {log_message} {self.status_code}')
        audit_log(logger, f'Failed: {log_message} {self.status_code}', AuditType.Fault)

    def get_val(self, argval, default):
        return self._kwargs.get(argval, default)
