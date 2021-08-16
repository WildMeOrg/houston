# -*- coding: utf-8 -*-
"""
Notifications database models
--------------------
"""

from app.extensions import db, HoustonModel

import enum
import uuid


class NotificationStatus(str, enum.Enum):
    read = 'read'
    unread = 'unread'


class NotificationType(str, enum.Enum):
    raw = 'raw'
    new_enc = 'new_enc'  # TODO what's this for?
    all = 'all'  # For use specifically in preferences, catchall for everything
    collab_request = 'collaboration request'
    merge_request = 'individual merge request'


# Can send messages out on multiple channels
class NotificationChannel(str, enum.Enum):
    rest = 'Rest API'
    email = 'email'


NOTIFICATION_DEFAULTS = {
    NotificationType.all: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.collab_request: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.merge_request: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
}

NOTIFICATION_FIELDS = {NotificationType.collab_request: {'requester'}}


class Notification(db.Model, HoustonModel):
    """
    Notifications database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    status = db.Column(
        db.String(length=255), default=NotificationStatus.unread, nullable=False
    )
    message_type = db.Column(db.String, default=NotificationType.raw, nullable=False)
    message_values = db.Column(db.JSON, nullable=True)
    recipient_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    recipient = db.relationship('User', back_populates='notifications')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'template={self.message_type}, '
            "recipient='{self.recipient}'"
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    # returns dictionary of channel:bool
    def channels_to_send(self):
        # pylint: disable=invalid-name
        channels = None
        user_prefs = UserNotificationPreferences.get_user_preferences(self.recipient)
        if self.message_type in user_prefs.keys():
            channels = user_prefs[self.message_type]

        return channels

    @classmethod
    def create(cls, notification_type, user, data):
        assert notification_type in NotificationType
        assert set(data.keys()) >= NOTIFICATION_FIELDS[notification_type]

        new_notification = cls(
            recipient=user,
            message_type=notification_type,
            message_values=data,
        )
        with db.session.begin(subtransactions=True):
            db.session.add(new_notification)
        # TODO Check if notification should be sent right now on any channels
        return new_notification


class NotificationPreferences(HoustonModel):
    """
    Notification Preferences database model.
    """

    # preferences Json Blob, 2D dictionary of Boolean values indexable first on NotificationType
    # and then NotificationChannel
    preferences = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    # Before updating free form JSON, ensure that it's valid
    def update_preference(self, notification_type, notification_channel, status):
        assert notification_type in NotificationType
        assert notification_channel in NotificationChannel
        assert isinstance(status, bool)
        self.preferences[notification_type][notification_channel] = status


class SystemNotificationPreferences(db.Model, NotificationPreferences):
    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    # A singleton
    @classmethod
    def get(cls):
        prefs = SystemNotificationPreferences.query.all()
        if len(prefs) == 0:
            system_prefs = cls(preferences=NOTIFICATION_DEFAULTS)
            with db.session.begin(subtransactions=True):
                db.session.add(system_prefs)
        else:
            system_prefs = prefs[0]
        return system_prefs


class UserNotificationPreferences(db.Model, NotificationPreferences):
    """
    User specific Notification Preferences database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    digest = db.Column(db.Boolean, default=False, nullable=False)

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    user = db.relationship('User', back_populates='notification_preferences')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "recipient='{self.user}'"
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def get_user_preferences(cls, user):
        prefs = SystemNotificationPreferences.get().preferences
        if user.notification_preferences:
            prefs.update(user.notification_preferences[0].preferences)
        return prefs
