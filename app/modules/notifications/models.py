# -*- coding: utf-8 -*-
"""
Notifications database models
--------------------
"""

from app.extensions import db, HoustonModel
from app.utils import HoustonException
from datetime import datetime  # NOQA

import enum
import uuid
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class NotificationType(str, enum.Enum):
    raw = 'raw'  # Dummy value used as a default
    new_enc = 'new_encounter_individual'  # A new encounter on an individual
    all = 'all'  # For use specifically in preferences, catchall for everything
    collab_request = 'collaboration_request'  # a user requests collaboration with you
    # other user approved collaboration request
    collab_approved = 'collaboration_approved'
    # other user requests edit collaboration with you
    collab_edit_request = 'collaboration_edit_request'
    # other user approved edit request
    collab_edit_approved = 'collaboration_edit_approved'
    # other user revokes the existing edit part of your collaboration
    collab_edit_revoke = 'collaboration_edit_revoke'
    collab_revoke = 'collaboration_revoke'  # other user revokes the collaboration
    # A user manager has created a collaboration for you with another user
    collab_manager_create = 'collaboration_manager_create'
    # A user manager has revoked a collaboration for you with another user
    collab_manager_revoke = 'collaboration_manager_revoke'
    individual_merge_request = 'individual_merge_request'
    individual_merge_complete = 'individual_merge_complete'


# Can send messages out on multiple channels
class NotificationChannel(str, enum.Enum):
    rest = 'restAPI'
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
    NotificationType.collab_approved: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.collab_edit_request: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.collab_edit_approved: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.collab_edit_revoke: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.collab_revoke: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.collab_manager_create: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.collab_manager_revoke: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.individual_merge_request: {
        NotificationChannel.rest: True,
        NotificationChannel.email: False,
    },
    NotificationType.individual_merge_complete: {
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
        'email_template_name': 'collaboration_request',
        'email_digest_content_template': 'collaboration_request_digest.jinja2',
        'mandatory_fields': {'collaboration_guid'},
    },
    NotificationType.collab_approved: {
        'email_template_name': 'collaboration_approved',
        'email_digest_content_template': 'collaboration_approved_digest.jinja2',
        'mandatory_fields': {'collaboration_guid'},
        'resolve_on_read': True,
    },
    NotificationType.collab_edit_request: {
        'email_template_name': 'collaboration_edit_request',
        'email_digest_content_template': 'collaboration_edit_request_digest',
        'mandatory_fields': {'collaboration_guid'},
    },
    NotificationType.collab_edit_approved: {
        'email_template_name': 'collaboration_edit_approved',
        'email_digest_content_template': 'collaboration_edit_approved_digest',
        'mandatory_fields': {'collaboration_guid'},
        'resolve_on_read': True,
    },
    NotificationType.collab_edit_revoke: {
        'email_template_name': 'collaboration_edit_revoke',
        'email_digest_content_template': 'collaboration_edit_revoke_digest',
        'mandatory_fields': {'collaboration_guid'},
        'resolve_on_read': True,
    },
    NotificationType.collab_revoke: {
        'email_template_name': 'collaboration_revoke',
        'email_digest_content_template': 'collaboration_revoke_digest',
        'mandatory_fields': {'collaboration_guid'},
        'resolve_on_read': True,
    },
    NotificationType.collab_manager_create: {
        'email_template_name': 'collaboration_manager_create',  # Not yet written
        'email_digest_content_template': 'collaboration_manager_create_digest',
        'mandatory_fields': {'collaboration_guid', 'user1_name', 'user2_name'},
        'allow_multiple': True,
        'resolve_on_read': True,
    },
    NotificationType.collab_manager_revoke: {
        'email_template_name': 'collaboration_manger_revoke',  # Not yet written
        'email_digest_content_template': 'collaboration_manager_revoke_digest',
        'mandatory_fields': {'collaboration_guid', 'user1_name', 'user2_name'},
        'allow_multiple': True,
        'resolve_on_read': True,
    },
    NotificationType.individual_merge_request: {
        'email_template_name': 'individual_merge_request',
        'email_digest_content_template': 'individual_merge_request_digest.jinja2',
        'mandatory_fields': {
            'request_id',
            'individual_list',
            'encounter_list',
        },
        'allow_multiple': True,
    },
    NotificationType.individual_merge_complete: {
        'email_template_name': 'individual_merge_complete',
        'email_digest_content_template': 'individual_merge_complete_digest.jinja2',
        'mandatory_fields': {
            'request_id',
            'individual_list',
            'encounter_list',
        },
        'allow_multiple': True,
        'resolve_on_read': True,
    },
    NotificationType.raw: {
        'email_template_name': 'raw',
        'email_digest_content_template': 'raw_digest.jinja2',
        'mandatory_fields': {},
    },
}


# Simple class to build up the contents of the message so that the caller does not need to know the field names above
class NotificationBuilder(object):
    def __init__(self, sender):
        self.sender = sender
        self.data = {}

    def set_collaboration(self, collab):
        self.data['collaboration_guid'] = collab.guid
        users = collab.get_users()
        assert len(users) == 2
        self.data['user1_name'] = users[0].full_name
        self.data['user2_name'] = users[1].full_name

    def set_individual_merge(self, individuals, encounters, request_data):
        self.data['individual_list'] = []
        for indiv in individuals:
            ind_data = {'guid': indiv.guid, 'primaryName': indiv.get_primary_name()}
            self.data['individual_list'].append(ind_data)
        self.data['encounter_list'] = []
        for enc in encounters:
            self.data['encounter_list'].append(enc.guid)
        self.data['request_id'] = request_data.get('id')
        # TODO other goodies in request_data


class Notification(db.Model, HoustonModel):
    """
    Notifications database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)

    message_type = db.Column(db.String, default=NotificationType.raw, nullable=False)
    message_values = db.Column(db.JSON, nullable=True)
    recipient_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    recipient = db.relationship('User', back_populates='notifications')
    sender_guid = db.Column(db.GUID, nullable=True)

    created = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'message_type={self.message_type}, '
            "recipient='{self.recipient}, '"
            "sender_guid='{self.sender_guid}'"
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @property
    def owner(self):
        return self.recipient

    @property
    def sender_name(self):
        return self.get_sender_name()

    def get_sender_name(self):
        from app.modules.users.models import User

        if self.sender_guid is not None:
            user = User.query.get(self.sender_guid)
            if user:
                return user.full_name

        return 'N/A'

    def get_sender_email(self):
        from app.modules.users.models import User

        user = User.query.get(self.sender_guid)
        if user:
            return user.email
        else:
            return 'N/A'

    # returns dictionary of channel:bool
    def channels_to_send(self, digest=False):
        # pylint: disable=invalid-name
        # In future the channels to send right now will be different for digest generation
        user_prefs = UserNotificationPreferences.get_user_preferences(self.recipient)
        channels = user_prefs.get(self.message_type, {})
        for name in channels:
            # If user set a channel to False in "all", it overrides the
            # local channel setting
            if not user_prefs[NotificationType.all].get(name, True):
                channels[name] = False

        return channels

    def send_if_required(self):
        from app.extensions.email import Email

        channels = self.channels_to_send(False)

        self._channels_sent = {}  # store what was sent out, if anything
        if channels[NotificationChannel.email]:
            config = NOTIFICATION_CONFIG[self.message_type]
            email_message_values = {
                'context_name': 'context not set',
                'sender_name': self.get_sender_name(),
                'sender_link': 'TBD',  # TODO will be fixed after some SiteSetting hackery
            }
            email_message_values.update(self.message_values)
            email = Email(recipients=[self.recipient])
            email.template(
                f"notifications/{config['email_template_name']}", **email_message_values
            )
            email.send_message()
            self._channels_sent[NotificationChannel.email.value] = email

    @classmethod
    def create(cls, notification_type, receiving_user, builder):
        assert notification_type in NotificationType
        config = NOTIFICATION_CONFIG[notification_type]
        data = builder.data

        assert set(data.keys()) >= set(config['mandatory_fields'])

        sender_guid = None
        if builder.sender and not builder.sender.is_anonymous:
            sender_guid = builder.sender.guid

        # prevent creation of a new notification if there is already an unread one
        existing_notifications = cls.query.filter_by(
            recipient=receiving_user,
            message_type=notification_type,
            sender_guid=sender_guid,
            is_read=False,
        ).all()

        if (
            len(existing_notifications)
            and 'allow_multiple' in config.keys()
            and not config['allow_multiple']
        ):
            log.info(f'reusing existing notification {existing_notifications[0]}')
            return existing_notifications[0]
        else:
            new_notification = cls(
                recipient=receiving_user,
                message_type=notification_type,
                message_values=data,
                sender_guid=sender_guid,
            )
            log.debug(f'Created new notification {new_notification}')
            with db.session.begin(subtransactions=True):
                db.session.add(new_notification)
            new_notification.send_if_required()
            return new_notification

    @classmethod
    def resolve_notification(self, notification_guid):
        notification = Notification.query.get(notification_guid)
        notification.is_resolved = True
        with db.session.begin(subtransactions=True):
            db.session.merge(notification)


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
        from .schemas import NotificationPreferenceSchema

        schema = NotificationPreferenceSchema()
        errors = schema.validate(new_prefs)
        if errors:
            raise HoustonException(log, schema.get_error_message(errors))


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
            changed = False
            for type_, defaults in NOTIFICATION_DEFAULTS.items():
                if type_ in system_prefs.preferences:
                    for key, value in defaults.items():
                        if key not in system_prefs.preferences[type_]:
                            system_prefs.preferences[type_][key] = value
                            changed = True
                else:
                    system_prefs.preferences[type_] = defaults
                    changed = True
            if changed:
                system_prefs.preferences = system_prefs.preferences
                with db.session.begin(subtransactions=True):
                    db.session.merge(system_prefs)
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
