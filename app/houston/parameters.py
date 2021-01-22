# -*- coding: utf-8 -*-
"""
RESTful API Parameters base class with password protection
--------------------------
"""
from flask_login import current_user
from flask_restplus_patched import PatchJSONParameters
from flask_restplus._http import HTTPStatus

from app.extensions.api import abort


# noinspection PyAbstractClass
class PatchJSONParametersWithPassword(PatchJSONParameters):
    """
    Base parameters class for handling PATCH arguments according to RFC 6902 with specific handling for
    password validation for some sensitive fields.
    Provides test, add and remove methods.
    Requires derived class to implement set_field and forget_field methods which return boolean of success state
    """

    # Some classes may require all fields to be password validated, some may require some.
    # If the SENSITIVE_FIELDS array is left as None, all fields are password protected
    SENSITIVE_FIELDS = None

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
        Some or all fields require extra permissions to be changed
        """
        if not cls.SENSITIVE_FIELDS or field in cls.SENSITIVE_FIELDS:
            if 'current_password' not in state:
                abort(
                    code=HTTPStatus.FORBIDDEN,
                    message='Updating database requires `current_password` test operation.',
                )
        return cls.set_field(obj, field, value, state)

    @classmethod
    def set_field(cls, obj, field, value, state):
        raise NotImplementedError()

    @classmethod
    def remove(cls, obj, field, value, state):
        if not cls.SENSITIVE_FIELDS or field in cls.SENSITIVE_FIELDS:
            if 'current_password' not in state:
                abort(
                    code=HTTPStatus.FORBIDDEN,
                    message='Updating database requires `current_password` test operation.',
                )
        return cls.forget_field(obj, field, value, state)

    @classmethod
    def forget_field(cls, obj, field, state):
        raise NotImplementedError()
