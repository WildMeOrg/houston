# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""

from app.extensions import FeatherModel, HoustonModel, db
import uuid
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SightingAssets(db.Model, HoustonModel):
    sighting_guid = db.Column(db.GUID, db.ForeignKey('sighting.guid'), primary_key=True)
    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)
    sighting = db.relationship('Sighting', back_populates='assets')
    asset = db.relationship('Asset')


class Sighting(db.Model, FeatherModel):
    """
    Sightings database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    assets = db.relationship('SightingAssets')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_owners(self):
        owners = []
        for encounter in self.get_encounters():
            if encounter.get_owner() is not None and encounter.get_owner() not in owners:
                owners.append(encounter.get_owner())
        return owners

    def get_owner(self):
        # this is what we talked about but it makes me squeamish
        if self.get_owners() is not None:
            return self.get_owners()[0]
        return None

    # will return None if not a single owner of all encounters (otherwise that user)
    def single_encounter_owner(self):
        single = None
        for encounter in self.encounters:
            if (
                single is not None and not single == encounter.owner
            ):  # basically a mismatch, so we fail
                return None
            if encounter.owner is not None:
                single = encounter.owner
        return single

    def user_owns_all_encounters(self, user):
        return user is not None and user == self.single_encounter_owner()

    def user_can_edit_all_encounters(self, user):
        return self.user_owns_all_encounters(user)

    def get_encounters(self):
        return self.encounters

    def add_encounter(self, encounter):
        if encounter not in self.encounters:
            self.encounters.append(encounter)

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
        rel = SightingAssets(sighting=self, asset=asset)
        db.session.add(rel)
        self.assets.append(rel)

    def add_asset_no_context(self, asset):
        rel = SightingAssets(sighting_guid=self.guid, asset_guid=asset.guid)
        self.assets.append(rel)

    def add_assets_no_context(self, asset_list):
        for asset in asset_list:
            self.add_asset_no_context(asset)

    def delete(self):
        with db.session.begin():
            db.session.delete(self)

    def delete_cascade(self):
        assets = self.get_assets()
        with db.session.begin(subtransactions=True):
            while self.assets:
                # this is actually removing the SightingAssets joining object (not the assets)
                db.session.delete(self.assets.pop())
            while self.encounters:
                enc = self.encounters.pop()
                enc.delete_cascade()
            db.session.delete(self)
            while assets:
                asset = assets.pop()
                asset.delete_cascade()

    def delete_from_edm(self, current_app):
        return Sighting.delete_from_edm_by_guid(current_app, self.guid)

    @classmethod
    def delete_from_edm_by_guid(cls, current_app, guid):
        assert guid is not None
        response = current_app.edm.request_passthrough(
            'sighting.data',
            'delete',
            {},
            guid,
        )
        return response

    # given edm_json (verbose json from edm) will populate with houston-specific data from feather object
    # note: this modifies the passed in edm_json, so not sure how legit that is?
    def augment_edm_json(self, edm_json):
        edm_json['createdHouston'] = self.created.isoformat()
        edm_json['updatedHouston'] = self.updated.isoformat()
        if (self.encounters is not None and edm_json['encounters'] is None) or (
            self.encounters is None and edm_json['encounters'] is not None
        ):
            log.warning('Only one None encounters value between edm/feather objects!')
        if self.encounters is not None and edm_json['encounters'] is not None:
            if len(self.encounters) != len(edm_json['encounters']):
                log.warning('Imbalanced encounters between edm/feather objects!')
                raise ValueError('imbalanced encounter count between edm/feather')
            else:
                i = 0
                while i < len(self.encounters):  # now we augment each encounter
                    found_edm = None
                    for edm_enc in edm_json['encounters']:
                        if edm_enc['id'] == str(self.encounters[i].guid):
                            found_edm = edm_enc
                    if found_edm is None:
                        raise ValueError(
                            f'could not find edm encounter matching {self.encounters[i]}'
                        )
                    self.encounters[i].augment_edm_json(found_edm)
                    i += 1
        if self.assets is None or len(self.assets) < 1:
            return edm_json
        from app.modules.assets.schemas import DetailedAssetSchema

        asset_schema = DetailedAssetSchema(many=False, only=('guid', 'filename', 'src'))
        edm_json['assets'] = []
        for asset in self.get_assets():
            json, err = asset_schema.dump(asset)
            edm_json['assets'].append(json)
        return edm_json

    # pass results-json for sighting.encounters from changes made (e.g. PATCH) and update houston encounters accordingly
    def rectify_edm_encounters(self, edm_encs_json):
        log.debug(f' RECTIFY IN {edm_encs_json}')
        edm_map = {}  # id => version of new results
        if edm_encs_json:
            for edm_enc in edm_encs_json:
                edm_map[edm_enc['id']] = edm_enc
        log.debug(f' RECTIFY EDM_MAP {edm_map}')
        # find which have been removed and which updated
        if self.encounters:
            for enc in self.encounters:
                if str(enc.guid) not in edm_map.keys():
                    # TODO candidate for audit log
                    log.info(f'houston Encounter {enc.guid} removed')
                    enc.delete_cascade()
                else:
                    if edm_map[str(enc.guid)]['version'] > enc.version:
                        log.debug(
                            f'houston Encounter {enc.guid} VERSION UPDATED {edm_map[str(enc.guid)]} > {enc.version}'
                        )
                    del edm_map[str(enc.guid)]
        # now any left should be new encounters from edm
        for enc_id in edm_map.keys():
            log.debug(
                f'houston Encounter {enc_id} NEWLY ADDED ENCOUNTER = {edm_map[enc_id]}'
            )
