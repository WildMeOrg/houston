# -*- coding: utf-8 -*-
"""
AccountRequest database models
--------------------
"""

import uuid

from app.extensions import HoustonModel, db


class AccountRequest(db.Model, HoustonModel):
    """
    AccountRequest database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    name = db.Column(db.String(length=255), index=True, nullable=False)
    email = db.Column(db.String(length=255), index=True, unique=False, nullable=False)
    message = db.Column(db.String, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'email={self.email}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )
