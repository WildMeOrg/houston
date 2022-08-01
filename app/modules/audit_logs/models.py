# -*- coding: utf-8 -*-
"""
Audit Logs database models
--------------------
"""

import logging
import uuid

from flask_login import current_user  # NOQA

from app.extensions import HoustonModel, db

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AuditLog(db.Model, HoustonModel):
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
            'audit_type={self.audit_type}, '
            "module ='{self.module_name}', "
            'item_guid={self.item_guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def query_search_term_hook(cls, term):
        from sqlalchemy import String
        from sqlalchemy_utils.functions import cast_if

        return (
            cast_if(cls.guid, String).contains(term),
            cls.module_name.contains(term),
            cast_if(cls.item_guid, String).contains(term),
            cls.user_email.contains(term),
            cls.message.contains(term),
            cls.audit_type.contains(term),
        )

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.audit_logs.schemas import DetailedAuditLogSchema

        return DetailedAuditLogSchema

    @classmethod
    def create(
        cls, msg, audit_type, module_name=None, item_guid=None, user=None, *args, **kwargs
    ):
        user_email = 'anonymous user'
        if user and not user.is_anonymous:
            user_email = user.email
        elif current_user and not current_user.is_anonymous:
            user_email = current_user.email

        # Some messages are enormous and we can only store so much data
        if len(msg) > 2500:
            # The start and the end are usually the most useful
            new_msg = msg[:1000]
            new_msg += '.....Text Removed.....'
            new_msg += msg[-1000:]
            log.warning(f'Truncating message. Was {len(msg)}, now {len(new_msg)}.')
            msg = new_msg

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
