# -*- coding: utf-8 -*-
"""
Serialization schemas for Notifications resources RESTful API
----------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from .models import Notification


class BaseNotificationSchema(ModelSchema):
    """
    Base Notification schema exposes only the most general fields.
    """

    sender_name = base_fields.Function(Notification.get_sender_name)
    sender_email = base_fields.Function(Notification.get_sender_email)

    class Meta:
        # pylint: disable=missing-docstring
        model = Notification
        fields = (
            Notification.guid.key,
            Notification.is_read.key,
            'sender_name',
            'sender_email',
            Notification.message_type.key,
        )
        dump_only = (Notification.guid.key,)


class DetailedNotificationSchema(BaseNotificationSchema):
    """
    Detailed Notification schema exposes all useful fields.
    """

    class Meta(BaseNotificationSchema.Meta):
        fields = BaseNotificationSchema.Meta.fields + (Notification.message_values.key,)
        dump_only = BaseNotificationSchema.Meta.dump_only + (
            Notification.message_values.key,
        )
