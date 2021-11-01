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

    social_groups = db.relationship(
        'SocialGroupIndividualMembership',
        back_populates='individual',
        order_by='SocialGroupIndividualMembership.individual_guid',
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
    def get_shared_sightings(self, *individuals):
        from app.modules.sightings.models import Sighting

        return Sighting.get_multiple(self.get_shared_sighting_guids(*individuals))

    # returns guids
    def get_shared_sighting_guids(self, *individuals):
        if not individuals or not isinstance(individuals, tuple) or len(individuals) < 1:
            raise ValueError('must be passed a tuple of at least 1 individual')
        include_me = (self,) + individuals
        return Individual.get_shared_sighting_guids_for_individual_guids(*include_me)

    @classmethod
    def get_shared_sighting_guids_for_individual_guids(cls, *individuals):
        if not individuals or not isinstance(individuals, tuple) or len(individuals) < 2:
            raise ValueError('must be passed a tuple of at least 2 individuals')
        from app.modules.sightings.models import Sighting
        from app.modules.encounters.models import Encounter
        from sqlalchemy.orm import aliased

        # we want guids strings here
        individual_guids = []
        for indiv in individuals:
            if isinstance(indiv, Individual):
                individual_guids.append(str(indiv.guid))
            else:
                individual_guids.append(str(indiv))
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

    # 0th individual will be the resultant/remaining individual
    @classmethod
    def merge(cls, *individuals, sex=None, primary_name=None):
        if not individuals or not isinstance(individuals, tuple) or len(individuals) < 2:
            raise ValueError('must be passed a tuple of at least 2 individuals')
        target_individual = individuals[0]
        source_individuals = individuals[1:]
        data = {
            'targetIndividualId': str(target_individual.guid),
            'sourceIndividualIds': [],
            'sex': sex,
            'primaryName': primary_name,
        }
        for indiv in source_individuals:
            data['sourceIndividualIds'].append(str(indiv.guid))
        # response = current_app.edm.request_passthrough_result(
        response = current_app.edm.request_passthrough(
            'individual.merge',
            'post',
            {
                'data': data,
                'headers': {'Content-Type': 'application/json'},
            },
            None,
        )
        if not response.ok:
            return response

        result = response.json()['result']
        error_msg = None
        if 'targetId' not in result or result['targetId'] != str(target_individual.guid):
            error_msg = 'edm merge-results targetId does not match target_individual.guid'
        elif (
            'merged' not in result
            or not isinstance(result['merged'], dict)
            or len(result['merged'].keys()) != len(source_individuals)
        ):
            error_msg = 'edm merge-results merged dict invalid'
        if error_msg:
            AuditLog.backend_fault(log, error_msg, target_individual)
            return

        # first we sanity-check the reported removed individuals vs what was requested
        for merged_id in result['merged'].keys():
            if merged_id not in data['sourceIndividualIds']:
                AuditLog.backend_fault(
                    log,
                    f'merge mismatch against sourceIndividualIds with {merged_id}',
                    target_individual,
                )
                return
            log.info(
                f"edm reports successful merge of indiv {merged_id} into {result['targetId']} for encounters {result['merged'][merged_id]}; adjusting locally"
            )
        # now we steal their encounters and delete them
        # NOTE:  technically we could iterate over the enc ids in merged.merged_id array, but we run (tiny) risk of this individual
        #   getting assigned to additional encounters in the interim, so instead we just steal all the encounters directly
        for indiv in source_individuals:
            for enc in indiv.encounters:
                AuditLog.audit_log_object(
                    log, indiv, f'assigning our {enc} to {target_individual}'
                )
                enc.individual_guid = target_individual.guid
            # TODO also consolidate SocialGroups
            indiv.delete()
        return result

    def merge_from(self, *individuals):
        all_indiv = (self,) + individuals
        return Individual.merge(*all_indiv)

    def delete(self):
        AuditLog.delete_object(log, self)
        with db.session.begin():
            for group in self.social_groups:
                db.session.delete(group)
            db.session.delete(self)

    def delete_from_edm(self):
        response = current_app.edm.request_passthrough(
            'individual.data',
            'delete',
            {},
            self.guid,
        )
        return response

    # this is basically identical to the method in Sighting, maybe can make generic util and just feed in a Schema?
    def augment_edm_json(self, edm_json):

        if (self.encounters is not None and edm_json['encounters'] is None) or (
            self.encounters is None and edm_json['encounters'] is not None
        ):
            log.warning('Only one None encounters value between edm/feather objects!')
        if self.encounters is not None and edm_json['encounters'] is not None:
            id_to_encounter = {e['id']: e for e in edm_json['encounters']}
            if set(str(e.guid) for e in self.encounters) != set(id_to_encounter):
                log.warning(
                    'Imbalanced encounters between edm/feather objects on sighting '
                    + str(self.guid)
                    + '!'
                )
                raise ValueError('imbalanced encounter count between edm/feather')

            from app.modules.encounters.schemas import (
                AugmentedIndividualApiEncounterSchema,
            )

            for encounter in self.encounters:  # now we augment each encounter
                found_edm = id_to_encounter[str(encounter.guid)]
                edm_schema = AugmentedIndividualApiEncounterSchema()
                found_edm.update(edm_schema.dump(encounter).data)

        return edm_json
