# -*- coding: utf-8 -*-
"""
Serialization schemas for Notifications resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from app.extensions import ExtraValidationSchema
from .models import Notification, NotificationType, NotificationChannel


class NotificationChannelSchema(ExtraValidationSchema):
    def __new__(cls, *args, **kwargs):
        for notification_channel in NotificationChannel.__members__.values():
            cls._declared_fields[notification_channel.value] = base_fields.Bool()
        return super().__new__(cls)


class NotificationPreferenceSchema(ExtraValidationSchema):
    def __new__(cls, *args, **kwargs):
        for notification_type in NotificationType.__members__.values():
            cls._declared_fields[notification_type.value] = base_fields.Nested(
                NotificationChannelSchema
            )
        return super().__new__(cls)


class BaseNotificationSchema(ModelSchema):
    """
    Base Notification schema exposes only the most general fields.
    """

    created = base_fields.DateTime()

    class Meta:
        # pylint: disable=missing-docstring
        model = Notification
        fields = (
            Notification.guid.key,
            Notification.is_read.key,
            Notification.is_resolved.key,
            'sender_name',
            Notification.sender_guid.key,
            Notification.message_type.key,
            Notification.created.key,
            'elasticsearchable',
            Notification.indexed.key,
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
