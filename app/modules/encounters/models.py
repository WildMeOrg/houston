# -*- coding: utf-8 -*-
"""
Encounters database models
--------------------
"""

from app.extensions import db, FeatherModel

import uuid


class Encounter(db.Model, FeatherModel):
    """
    Encounters database model.
    """

    owner = db.Column(db.GUID, default=uuid.uuid4, nullable=True)

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    sighting_id = db.Column(db.Integer, db.ForeignKey('sighting.guid'))

    title = db.Column(db.String(length=50), nullable=False)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "title='{self.title},'"
            'owner={self.owner},'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    def get_owner(self):
        return self.owner

    def get_sighting(self):
        return self.sighting
