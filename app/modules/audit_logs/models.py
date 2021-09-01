# -*- coding: utf-8 -*-
"""
Audit Logs database models
--------------------
"""

from sqlalchemy_utils import Timestamp

from app.extensions import db

import uuid


class AuditLog(db.Model, Timestamp):
    """
    Audit Logs database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    module_name = db.Column(db.String(length=50), nullable=True)

    # Item and user guids intentionally not backrefs to other models as we want to maintain the log even after
    # the item has been removed
    item_guid = db.Column(db.GUID, nullable=True)
    user_email = db.Column(db.String(length=120), nullable=False)

    message = db.Column(db.String(length=240), nullable=True)
    # One of AuditType
    audit_type = db.Column(db.String, nullable=False)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "module ='{self.module_name}', "
            'item_guid={self.item_guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def create(cls, msg, audit_type, user_email, module_name=None, item_guid=None):

        # only store max 240 chars
        if len(msg) > 240:
            msg = msg[0:240]

        if module_name or item_guid:
            # Must set both of them or neither
            assert item_guid
            assert module_name
            log_entry = AuditLog(
                module_name=module_name,
                item_guid=item_guid,
                user_email=user_email,
                message=msg,
                audit_type=audit_type,
            )
        else:
            log_entry = AuditLog(
                user_email=user_email, message=msg, audit_type=audit_type
            )

        with db.session.begin(subtransactions=True):
            db.session.add(log_entry)
