# -*- coding: utf-8 -*-
"""
Keywords database models
--------------------
"""

from app.extensions import db, HoustonModel

import uuid


class Keyword(db.Model, HoustonModel):
    """
    Keywords database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    value = db.Column(db.String, nullable=False)

    def get_value(self):
        return self.value

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'value={self.value}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def delete(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)
