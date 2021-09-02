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
