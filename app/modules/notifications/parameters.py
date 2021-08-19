# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Notifications resources RESTful API
-----------------------------------------------------------
"""


from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import Notification  # NOQA


class CreateNotificationParameters(Parameters, schemas.DetailedNotificationSchema):
    class Meta(schemas.DetailedNotificationSchema.Meta):
        pass


class PatchNotificationDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
    )

    PATH_CHOICES = ('/is_read',)

    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False

        if field == 'is_read':
            if isinstance(value, bool):
                obj.is_read = value
                ret_val = True

        return ret_val
