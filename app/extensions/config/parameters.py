# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-order
"""
Input arguments (Parameters) for User resources RESTful API
-----------------------------------------------------------
"""

from flask_login import current_user
from flask_restplus_patched import PatchJSONParameters
from flask_restplus._http import HTTPStatus

from app.extensions import _CONFIG_PATH_CHOICES
from app.extensions.api import abort

from .models import HoustonConfig

import logging


log = logging.getLogger(__name__)


class PatchHoustonConfigParameters(PatchJSONParameters):
    # pylint: disable=abstract-method
    """
    User details updating parameters following PATCH JSON RFC.
    """

    VALID_FIELDS = _CONFIG_PATH_CHOICES + ['current_password']

    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def test(cls, obj, field, value, state):
        if field == 'current_password':
            if current_user.password == value:
                state['current_password'] = value
                return True
            else:
                abort(code=HTTPStatus.FORBIDDEN, message='Wrong password')

        return PatchJSONParameters.test(obj, field, value, state)

    @classmethod
    def add(cls, obj, field, value, state):
        """
        Some fields require extra permissions to be changed.

        Changing `is_active` and `is_staff` properties, current user
        must be a supervisor of the changing user, and `current_password` of
        the current user should be provided.

        Changing `is_admin` property requires current user to be Admin, and
        `current_password` of the current user should be provided..
        """
        if 'current_password' not in state:
            abort(
                code=HTTPStatus.FORBIDDEN,
                message='Updating database config requires `current_password` test operation.',
            )
        HoustonConfig.set(field, value)
        return True

    @classmethod
    def remove(cls, obj, field, state):
        if 'current_password' not in state:
            abort(
                code=HTTPStatus.FORBIDDEN,
                message='Updating database config requires `current_password` test operation.',
            )
        HoustonConfig.forget(field)
        return True

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
