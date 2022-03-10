# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Notifications resources RESTful API
-----------------------------------------------------------
"""


from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import Notification, NOTIFICATION_CONFIG  # NOQA
from app.extensions.api.parameters import PaginationParameters
from flask_marshmallow import base_fields


class ListAllUnreadNotifications(PaginationParameters):
    sort = base_fields.String(
        description='the field to sort the results by, default is "created"',
        missing='created',
    )
    reverse = base_fields.Boolean(
        description='the field to reverse the sorted results (before paging has been performed), default is True',
        missing=True,
    )


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
            resolve_on_read = NOTIFICATION_CONFIG[obj.message_type].get(
                'resolve_on_read', False
            )
            if isinstance(value, bool):
                obj.is_read = value
                ret_val = True
                if value is True and resolve_on_read:
                    obj.is_resolved = True

        return ret_val
