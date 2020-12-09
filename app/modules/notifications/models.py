# -*- coding: utf-8 -*-
"""
Notifications database models
--------------------
"""

from app.extensions import db, HoustonModel
from sqlalchemy.sql import func

import enum
import uuid


class NotificationStatus(str, enum.Enum):
    read = 'read'
    unread = 'unread'


class NotificationMessageTemplate(str, enum.Enum):
    raw = 'raw'
    new_enc = 'new_enc'
    collab_request = 'collab_request'


class Notification(db.Model, HoustonModel):
    """
    Notifications database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    timestamp = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    status = db.Column(
        db.String(length=255), default=NotificationStatus.unread, nullable=False
    )
    message_template = db.Column(
        db.String, default=NotificationMessageTemplate.raw, nullable=False
    )
    message_values = db.Column(db.JSON, nullable=True)
    recipient_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    recipient = db.relationship('User')
    # recipient = db.relationship('User', backref=db.backref('notifications'))

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.id}, '
            'template={self.message_template}, '
            "recipient='{self.recipient}'"
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )
