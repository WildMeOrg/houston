# -*- coding: utf-8 -*-
"""
Audit Logs database models
--------------------
"""

from flask_login import current_user  # NOQA
from app.extensions import db, Timestamp

import uuid


class AuditLog(db.Model, Timestamp):
    """
    Audit Logs database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    module_name = db.Column(db.String(length=50), index=True, nullable=True)

    # Item and user guids intentionally not backrefs to other models as we want to maintain the log even after
    # the item has been removed
    item_guid = db.Column(db.GUID, index=True, nullable=True)
    user_email = db.Column(db.String(), nullable=False)

    message = db.Column(db.String(), index=True, nullable=True)

    # One of AuditType
    audit_type = db.Column(db.String, index=True, nullable=False)

    # How long did the operation take
    duration = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "module ='{self.module_name}', "
            'item_guid={self.item_guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def create(
        cls, msg, audit_type, module_name=None, item_guid=None, user=None, *args, **kwargs
    ):

        user_email = 'anonymous user'
        if user and not user.is_anonymous:
            user_email = user.email
        elif current_user and not current_user.is_anonymous:
            user_email = current_user.email

        duration = None
        if 'duration' in kwargs:
            duration = kwargs['duration']

        if module_name or item_guid:
            # Must set both of them or neither
            assert item_guid and module_name
            log_entry = AuditLog(
                module_name=module_name,
                item_guid=item_guid,
                user_email=user_email,
                message=msg,
                audit_type=audit_type,
                duration=duration,
            )
        else:
            log_entry = AuditLog(
                user_email=user_email,
                message=msg,
                audit_type=audit_type,
                duration=duration,
            )

        with db.session.begin(subtransactions=True):
            db.session.add(log_entry)
