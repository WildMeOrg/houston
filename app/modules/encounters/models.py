# -*- coding: utf-8 -*-
"""
Encounters database models
--------------------
"""

from app.extensions import db, FeatherModel, HoustonModel
from app.modules.individuals.models import Individual

from app.modules.asset_groups import models as submissions_models  # NOQA
from app.modules.assets import models as assets_models  # NOQA


import uuid


class EncounterAssets(db.Model, HoustonModel):
    encounter_guid = db.Column(db.GUID, db.ForeignKey('encounter.guid'), primary_key=True)
    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)
    encounter = db.relationship('Encounter', back_populates='assets')
    asset = db.relationship('Asset')


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

    from app.modules.individuals.models import Individual

    individual_guid = db.Column(
        db.GUID, db.ForeignKey('individual.guid'), index=True, nullable=True
    )
    individual = db.relationship('Individual', backref=db.backref('encounters'))

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    owner = db.relationship(
        'User', backref=db.backref('owned_encounters'), foreign_keys=[owner_guid]
    )

    submitter_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    submitter = db.relationship(
        'User', backref=db.backref('submitted_encounters'), foreign_keys=[submitter_guid]
    )

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

    # not going to check for ownership by User.get_public_user() because:
    #  a) this allows for other-user-owned data to be toggled to public
    #  b) allows for us to _disallow_ public access to public-user-owned data
    def set_individual(self, individual):
        if isinstance(individual, Individual):
            self.individual = individual

    def is_public(self):
        return self.public

    def get_assets(self):
        return [ref.asset for ref in self.assets]

    def add_asset(self, asset):
        with db.session.begin(subtransactions=True):
            self.add_asset_in_context(asset)

    def add_assets(self, asset_list):
        with db.session.begin():
            for asset in asset_list:
                self.add_asset_in_context(asset)

    def add_asset_in_context(self, asset):
        rel = EncounterAssets(encounter=self, asset=asset)
        db.session.add(rel)
        self.assets.append(rel)

    def add_asset_no_context(self, asset):
        rel = EncounterAssets(encounter_guid=self.guid, asset_guid=asset.guid)
        self.assets.append(rel)

    def add_assets_no_context(self, asset_list):
        for asset in asset_list:
            self.add_asset_no_context(asset)

    # we dont delete .assets here because that is complex (due to annotations)
    def delete(self):
        with db.session.begin():
            while self.assets:
                # this is actually removing the EncounterAssets joining object (not the assets)
                db.session.delete(self.assets.pop())
            db.session.delete(self)

    def delete_cascade(self):
        assets = self.get_assets()
        # TODO modify behavior when we have annotations
        with db.session.begin(subtransactions=True):
            while self.assets:
                # this is actually removing the EncounterAssets joining object (not the assets)
                db.session.delete(self.assets.pop())
            db.session.delete(self)
        while assets:
            asset = assets.pop()
            asset.delete_cascade()

    def delete_from_edm(self, current_app):
        response = current_app.edm.request_passthrough(
            'encounter.data',
            'delete',
            {},
            self.guid,
        )
        return response

    # given edm_json (verbose json from edm) will populate with houston-specific data from feather object
    # note: this modifies the passed in edm_json, so not sure how legit that is?
    def augment_edm_json(self, edm_json):
        edm_json['createdHouston'] = self.created.isoformat()
        edm_json['updatedHouston'] = self.updated.isoformat()
        from app.modules.users.schemas import PublicUserSchema

        user_schema = PublicUserSchema(many=False)
        json, err = user_schema.dump(self.get_owner())
        edm_json['owner'] = json
        if self.submitter_guid is not None:
            json, err = user_schema.dump(self.submitter)
            edm_json['submitter'] = json

        if self.assets is None or len(self.assets) < 1:
            return edm_json
        from app.modules.assets.schemas import DetailedAssetSchema

        asset_schema = DetailedAssetSchema(many=False, only=('guid', 'filename', 'src'))
        edm_json['assets'] = []
        for asset in self.get_assets():
            json, err = asset_schema.dump(asset)
            edm_json['assets'].append(json)
        return edm_json
