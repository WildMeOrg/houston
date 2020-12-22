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

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    from app.modules.sightings.models import Sighting

    sighting_guid = db.Column(
        db.GUID, db.ForeignKey('sighting.guid'), index=True, nullable=True
    )
    sighting = db.relationship('Sighting', backref=db.backref('encounters'))

    owner_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    owner = db.relationship('User', backref=db.backref('owned_encounters'))

    title = db.Column(db.String(length=50), nullable=False)


    public = db.Column(db.Boolean, default=False, nullable=False)

    projects = db.relationship('ProjectEncounter', back_populates='encounter')

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

    def is_public(self):
        if self.public is True or self.owner is None:
            return True

    def has_read_permission(self, obj):
        # todo, check if the encounter owns the sighting once Colin's sightings code is merged in
        # if isinstance(obj, Sighting):
        # check sightings array
        # else look to see if the object is owned by any sighting
        return False
