# -*- coding: utf-8 -*-
"""
Notifications database models
--------------------
"""

from app.extensions import db, HoustonModel
from flask import render_template
from app.utils import HoustonException

import enum
import uuid


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

NOTIFICATION_CONFIG = {
    # All messages must have a sender
    NotificationType.all: {
        'mandatory_fields': {'sender_name', 'sender_email'},
    },
    NotificationType.collab_request: {
        'email_content_template': 'collaboration_request.jinja2',
        'email_digest_content_template': 'collaboration_request_digest.jinja2',
        'email_subject_template': 'collaboration_request_subject.jinja2',
        'mandatory_fields': {'collaboration_guid'},
    },
    NotificationType.raw: {
        'email_content_template': 'raw.jinja2',
        'email_digest_content_template': 'raw_digest.jinja2',
        'email_subject_template': 'raw_subject.jinja2',
        'mandatory_fields': {},
    },
}


# Simple class to build up the contents of the message so that the caller does not need to know the field names above
class NotificationBuilder(object):
    def __init__(self, sender):
        self.data = {'sender_name': sender.full_name, 'sender_email': sender.email}

    def set_collaboration(self, collab):
        self.data['collaboration_guid'] = collab.guid


class Notification(db.Model, HoustonModel):
    """
    Notifications database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    is_read = db.Column(db.Boolean, default=False, nullable=False)

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

    @property
    def owner(self):
        return self.recipient

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
            for name in channels.keys():
                # Don't blame me, I tried to make this line more readable, brunette insisted that it
                # was more readable when the params were nowhere near the function name
                if channels[name] and not user_prefs[NotificationType.all].get(
                    name, True
                ):
                    channels[name] = False

        return channels

    def send_if_required(self):
        from app.modules.emails.utils import EmailUtils

        channels = self.channels_to_send(False)

        if channels[NotificationChannel.email]:
            config = NOTIFICATION_CONFIG[self.message_type]
            email_message_values = {
                'context_name': 'context not set',
            }
            email_message_values.update(self.message_values)
            subject_template = f"email/en/{config['email_subject_template']}"
            content_template = f"email/en/{config['email_content_template']}"
            subject = render_template(subject_template, **email_message_values)
            email_content = render_template(content_template, **email_message_values)
            EmailUtils.send_email(
                self.message_values['sender_email'],
                self.recipient.email,
                subject,
                email_content,
            )

    @classmethod
    def create(cls, notification_type, receiving_user, builder):
        assert notification_type in NotificationType

        data = builder.data
        assert set(data.keys()) >= set(
            NOTIFICATION_CONFIG[NotificationType.all]['mandatory_fields']
        )
        assert set(data.keys()) >= set(
            NOTIFICATION_CONFIG[notification_type]['mandatory_fields']
        )

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

    @classmethod
    def validate_preferences(cls, new_prefs):
        valid_types = set([pref.name for pref in NotificationType])
        if isinstance(new_prefs, dict) and set(new_prefs.keys()) <= valid_types:
            for new_pref_type in new_prefs:
                valid_channels = set([pref.name for pref in NotificationChannel])
                if not (
                    isinstance(new_pref_type, dict)
                    and set(new_pref_type.keys()) <= valid_channels
                ):
                    raise HoustonException(
                        log_message=f'Invalid Notification channel, options are {valid_channels}'
                    )
                else:
                    for new_chan in new_pref_type:
                        if not isinstance(new_chan.value, bool):
                            raise HoustonException(
                                log_message='all values set in NotificationPreferences must be boolean '
                            )
        else:
            raise HoustonException(
                log_message=f'Invalid Notification Type, options are {valid_types}'
            )


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
