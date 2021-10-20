# -*- coding: utf-8 -*-
"""
Individuals database models
--------------------
"""

from app.extensions import FeatherModel, db
from flask import current_app
import uuid
import logging
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Individual(db.Model, FeatherModel):
    """
    Individuals database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    featured_asset_guid = db.Column(db.GUID, default=None, nullable=True)

    version = db.Column(db.BigInteger, default=None, nullable=True)

    encounters = db.relationship(
        'Encounter', back_populates='individual', order_by='Encounter.guid'
    )

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_encounters(self):
        return self.encounters

    def add_encounters(self, encounters):
        for encounter in encounters:
            if encounter not in self.get_encounters():
                self.encounters.append(encounter)

    def add_encounter(self, encounter):
        self.add_encounters([encounter])

    def remove_encounter(self, encounter):
        if encounter in self.get_encounters():
            self.encounters.remove(encounter)

            # If an individual has not been encountered, it does not exist
            # Although... I'm not satisfied with this. Auto delete only if the object is persisted? Hmm...
            # TODO Fix this
            # if len(self.encounters) == 0 and  Individual.query.get(self.guid) is not None:
            #     self.delete_from_edm(current_app)
            #     self.delete()

    def get_members(self):
        return [encounter.owner for encounter in self.encounters]

    def get_featured_asset_guid(self):
        rt_val = None
        if self.featured_asset_guid is not None:
            if self._ensure_asset_individual_association(self.featured_asset_guid):
                rt_val = self.featured_asset_guid
        elif len(self.encounters) > 0 and self.encounters[0].annotations is not None:
            from app.modules.encounters.models import Encounter

            encounter = Encounter.query.get(self.encounters[0].guid)

            if len(encounter.annotations) > 0:
                assert encounter.annotations[0].asset_guid
                rt_val = self.encounters[0].annotations[0].asset_guid
        return rt_val

    # returns Individuals
    def get_cooccurring_individuals(self):
        return Individual.get_multiple(self.get_cooccurring_individual_guids())

    # returns guids
    def get_cooccurring_individual_guids(self):
        return Individual.get_cooccurring_individual_guids_for_individual_guid(self.guid)

    # arbitrary individual_guid
    @classmethod
    def get_cooccurring_individual_guids_for_individual_guid(cls, individual_guid):
        from app.modules.sightings.models import Sighting
        from app.modules.encounters.models import Encounter
        from sqlalchemy.orm import aliased

        enc1 = aliased(Encounter, name='enc1')
        enc2 = aliased(Encounter, name='enc2')
        res = (
            db.session.query(enc1.individual_guid)
            .join(Sighting)
            .join(enc2)
            .filter(enc2.individual_guid == individual_guid)
            .filter(enc1.individual_guid != individual_guid)
            .group_by(enc1.individual_guid)
        )
        return [row.individual_guid for row in res]

    # returns Sightings
    def get_shared_sightings(self, individual_guids):
        from app.modules.sightings.models import Sighting

        return Sighting.get_multiple(self.get_shared_sighting_guids(individual_guids))

    # returns guids
    def get_shared_sighting_guids(self, individual_guids):
        if (
            not individual_guids
            or not isinstance(individual_guids, list)
            or len(individual_guids) < 1
        ):
            raise ValueError('must be passed a list of at least 1 individual guid')
        individual_guids.append(self.guid)
        return Individual.get_shared_sighting_guids_for_individual_guids(individual_guids)

    @classmethod
    def get_shared_sighting_guids_for_individual_guids(self, individual_guids):
        if (
            not individual_guids
            or not isinstance(individual_guids, list)
            or len(individual_guids) < 2
        ):
            raise ValueError('must be passed a list of at least 2 individual guids')
        from app.modules.sightings.models import Sighting
        from app.modules.encounters.models import Encounter
        from sqlalchemy.orm import aliased

        alias = []
        res = db.session.query(Sighting.guid)
        for i in range(len(individual_guids)):
            alias.append(aliased(Encounter, name=f'enc{i}'))
            res = res.join(alias[i])
        for i in range(len(individual_guids)):
            res = res.filter(alias[i].individual_guid == individual_guids[i])
        return [row.guid for row in res]

    def set_featured_asset_guid(self, asset_guid):
        if self._ensure_asset_individual_association(asset_guid):
            self.featured_asset_guid = asset_guid

    def _ensure_asset_individual_association(self, asset_guid):

        rt_val = False
        from app.modules.assets.models import Asset

        asset = Asset.find(asset_guid)
        if asset and asset.annotations:
            for annotation in asset.annotations:
                if annotation.encounter.individual_guid == self.guid:
                    rt_val = True
        return rt_val

    def delete(self):
        AuditLog.delete_object(log, self)
        with db.session.begin():
            db.session.delete(self)

    def delete_from_edm(self):
        response = current_app.edm.request_passthrough(
            'individual.data',
            'delete',
            {},
            self.guid,
        )
        return response
