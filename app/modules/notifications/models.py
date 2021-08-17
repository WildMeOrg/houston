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
    new_enc = 'new_encounter_individual'  # A new encounter on an individual
    all = 'all'  # For use specifically in preferences, catchall for everything
    collab_request = 'collaboration_request'
    merge_request = 'individual_merge_request'


# Can send messages out on multiple channels
class NotificationChannel(str, enum.Enum):
    rest = 'Rest API'
    email = 'email'


NOTIFICATION_DEFAULTS = {
    NotificationType.all: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.raw: {
        NotificationChannel.rest: True,
        NotificationChannel.email: True,
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

NOTIFICATION_FIELDS = {
    NotificationType.collab_request: {'sender_name', 'sender_email'},
    NotificationType.raw: {'sender_name', 'sender_email'},
}


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

    def get_sender_name(self):
        return self.message_values.get('sender_name', 'N/A')

    def get_sender_email(self):
        return self.message_values.get('sender_email', 'N/A')

    # returns dictionary of channel:bool
    def channels_to_send(self, digest=False):
        # pylint: disable=invalid-name
        # In future the channels to send right now will be different for digest generation
        channels = None
        user_prefs = UserNotificationPreferences.get_user_preferences(self.recipient)
        if self.message_type in user_prefs.keys():
            channels = user_prefs[self.message_type]

        return channels

    def send_if_required(self):
        from app.modules.emails.utils import EmailUtils

        channels = self.channels_to_send(False)
        if channels[NotificationChannel.email]:
            # presumes that each string NotificationType has a matching string EmailType, will be caught by
            # assert if not
            outgoing_message = EmailUtils.build_email(
                self.message_type, self.message_values
            )
            EmailUtils.send_email(outgoing_message)

    @classmethod
    def create(cls, notification_type, sending_user, receiving_user, data):
        assert notification_type in NotificationType

        if sending_user:
            data['sender_name'] = sending_user.full_name
            data['sender_email'] = sending_user.email

        assert set(data.keys()) >= set(NOTIFICATION_FIELDS[notification_type])

        new_notification = cls(
            recipient=receiving_user,
            message_type=notification_type,
            message_values=data,
        )
        with db.session.begin(subtransactions=True):
            db.session.add(new_notification)
        new_notification.send_if_required()
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
