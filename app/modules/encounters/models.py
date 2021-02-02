# -*- coding: utf-8 -*-
"""
Encounters database models
--------------------
"""

from app.extensions import db, FeatherModel, HoustonModel

# from app.modules.assets import models as assets_models  # NOQA


import uuid


class EncounterAssets(db.Model, HoustonModel):
    encounter_guid = db.Column(db.GUID, db.ForeignKey('encounter.guid'), primary_key=True)
    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)
    encounters = db.relationship('Encounter', back_populates='assets')
    # assets = db.relationship('Asset', back_populates='encounters')
    assets = db.relationship('Asset')


class Encounter(db.Model, FeatherModel):
    """
    Encounters database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    from app.modules.sightings.models import Sighting

    sighting_guid = db.Column(
        db.GUID, db.ForeignKey('sighting.guid'), index=True, nullable=True
    )
    sighting = db.relationship('Sighting', backref=db.backref('encounters'))

    owner_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    owner = db.relationship('User', backref=db.backref('owned_encounters'))

    public = db.Column(db.Boolean, default=False, nullable=False)

    projects = db.relationship('ProjectEncounter', back_populates='encounter')

    assets = db.relationship('EncounterAssets')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'version={self.version}, '
            'owner={self.owner},'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

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
