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
from datetime import datetime

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class IndividualMergeRequestVote(db.Model):
    """
    Records a vote on a Merge Request
    """

    # we dont really need a primary key on this table, but sqlalchemy pretty much requires one; so we
    #   get ours with (request_id + user_guid + created) which should be unique enough thanks to timestamp
    request_id = db.Column(db.GUID, index=True, nullable=False, primary_key=True)
    user_guid = db.Column(
        db.GUID,
        db.ForeignKey('user.guid'),
        index=True,
        nullable=False,
        primary_key=True,
    )
    user = db.relationship('User', foreign_keys=[user_guid])
    vote = db.Column(db.String(length=10), index=True, nullable=False)
    created = db.Column(
        db.DateTime, index=True, default=datetime.utcnow, nullable=False, primary_key=True
    )

    def __repr__(self):
        return (
            '<{class_name}('
            'req={self.request_id}, '
            "user='{self.user_guid}', "
            'vote={self.vote}, '
            'date={self.created}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def record_vote(cls, request_id, user, vote):
        req_vote = IndividualMergeRequestVote(
            request_id=request_id,
            user_guid=user.guid,
            vote=vote,
        )
        with db.session.begin(subtransactions=True):
            db.session.add(req_vote)
        return req_vote

    @classmethod
    def get_voters(cls, request_id):
        from app.modules.users.models import User

        res = (
            db.session.query(IndividualMergeRequestVote.user_guid)
            .filter(IndividualMergeRequestVote.request_id == request_id)
            .group_by(IndividualMergeRequestVote.user_guid)
        )
        return [User.query.get(uid) for uid in res]


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

    def merge_from(self, *source_individuals, sex=None, primary_name=None):
        if (
            not source_individuals
            or not isinstance(source_individuals, tuple)
            or len(source_individuals) < 1
        ):
            raise ValueError('must be passed a tuple of at least 1 individual')
        data = {
            'targetIndividualId': str(self.guid),
            'sourceIndividualIds': [],
            'sex': sex,
            'primaryName': primary_name,
        }
        for indiv in source_individuals:
            data['sourceIndividualIds'].append(str(indiv.guid))
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
            AuditLog.backend_fault(
                log,
                f'non-OK ({response.status_code}) response from edm: {response.json()}',
                self,
            )
            return response

        result = response.json()['result']
        error_msg = None
        if 'targetId' not in result or result['targetId'] != str(self.guid):
            error_msg = 'edm merge-results targetId does not match self.guid'
        elif (
            'merged' not in result
            or not isinstance(result['merged'], dict)
            or len(result['merged'].keys()) != len(source_individuals)
        ):
            error_msg = 'edm merge-results merged dict invalid'
        if error_msg:
            AuditLog.backend_fault(log, error_msg, self)
            raise ValueError(error_msg)

        # first we sanity-check the reported removed individuals vs what was requested
        for merged_id in result['merged'].keys():
            if merged_id not in data['sourceIndividualIds']:
                error_msg = f'merge mismatch against sourceIndividualIds with {merged_id}'
                AuditLog.backend_fault(log, error_msg, self)
                raise ValueError(error_msg)
            log.info(
                f"edm reports successful merge of indiv {merged_id} into {result['targetId']} for encounters {result['merged'][merged_id]}; adjusting locally"
            )
        # now we steal their encounters and delete them
        # NOTE:  technically we could iterate over the enc ids in merged.merged_id array, but we run (tiny) risk of this individual
        #   getting assigned to additional encounters in the interim, so instead we just steal all the encounters directly
        for indiv in source_individuals:
            for enc in indiv.encounters:
                AuditLog.audit_log_object(
                    log, indiv, f'merge assigning our {enc} to {self}'
                )
                AuditLog.audit_log_object(
                    log, self, f'assigned {enc} from merged {indiv}'
                )
                enc.individual_guid = self.guid
            self._consolidate_social_groups(indiv)
            indiv.delete()
        AuditLog.audit_log_object(
            log,
            self,
            f"merge SUCCESS from {data['sourceIndividualIds']}",
        )
        return result

    # mimics individual.merge_from(), but does not immediately executes; rather waits for approval
    #   and initiates a request including time-out etc
    # - really likely only useful via api endpoint (based on permissions); not direct call
    # - just a light wrapper to _merge_request_init()
    def merge_request_from(self, source_individuals, parameters=None):
        res = self._merge_request_init(source_individuals, parameters)
        Individual.merge_request_notify([self] + source_individuals, res)
        return res

    # note: for merge_complete individuals will only contain target individual, but
    #   request_data should contain key from_individual_ids
    @classmethod
    def merge_request_notify(cls, individuals, request_data, notif_type=None):
        from flask_login import current_user
        from app.modules.notifications.models import NotificationType

        if not notif_type:
            notif_type = NotificationType.merge_request
        owners = {}
        for indiv in individuals:
            for enc in indiv.encounters:
                # we only skip current_user when it is merge_request (merge_complete goes to all users)
                if not enc.owner or (
                    notif_type == NotificationType.merge_request
                    and enc.owner == current_user
                ):
                    continue
                if enc.owner not in owners:
                    owners[enc.owner] = {'individuals': set(), 'encounters': set()}
                owners[enc.owner]['individuals'].add(indiv)
                owners[enc.owner]['encounters'].add(enc)
        log.debug(
            f'merge_request_notify() type={notif_type} created owners structure {owners}'
        )
        for owner in owners:
            Individual._merge_request_notify_user(
                current_user,
                owner,
                owners[owner]['individuals'],
                owners[owner]['encounters'],
                request_data,
                notif_type,
            )

    @classmethod
    def _merge_request_notify_user(
        cls, sender, user, individuals, encounters, request_data, notif_type
    ):
        from app.modules.notifications.models import (
            Notification,
            NotificationBuilder,
        )

        builder = NotificationBuilder(sender)
        builder.set_merge_request(individuals, encounters, request_data)
        notification = Notification.create(notif_type, user, builder)
        log_msg = (
            f'merge request: notification {notification} from {sender} re: {individuals}'
        )
        AuditLog.audit_log_object(log, user, log_msg)

    @classmethod
    def merge_request_cancel_task(cls, req_id):
        current_app.celery.control.revoke(req_id)
        Individual.merge_request_cleanup(req_id)

    # scrubs notifications etc, once a merge has completed
    @classmethod
    def merge_request_cleanup(cls, req_id):
        log.debug(
            f'[{req_id}] merge_request_cleanup (notifications, etc) not yet implemented'
        )

    def get_blocking_encounters(self):
        blocking = []
        for enc in self.encounters:
            if not enc.current_user_has_edit_permission():
                blocking.append(enc)
        return blocking

    def _consolidate_social_groups(self, source_individual):
        if not source_individual.social_groups:
            return
        for source_member in source_individual.social_groups:
            socgrp = source_member.social_group
            already_member = socgrp.get_member(str(self.guid))
            data = {'roles': source_member.roles}  # roles may be empty, this is fine
            # must blow away source_member roles in case one is singular (as it will get passed to target)
            source_member.roles = None
            with db.session.begin(subtransactions=True):
                db.session.merge(source_member)
            if already_member:
                socgrp.add_roles(str(self.guid), data.get('roles'))
            else:
                socgrp.add_member(str(self.guid), data)
            AuditLog.audit_log_object(
                log,
                self,
                f"merge passing membership to {socgrp} from {source_individual} [roles {data.get('roles')}]",
            )

    # this might end up being a SiteSetting etc
    @classmethod
    def get_merge_request_deadline_days(cls):
        return 14

    # does the actual work of setting up celery task to execute this merge
    # NOTE: this does not do any notification of users; see merge_request_from()
    def _merge_request_init(self, individuals, parameters=None):
        from app.modules.individuals.tasks import execute_merge_request
        from datetime import datetime, timedelta

        if not individuals or not isinstance(individuals, list) or len(individuals) < 1:
            msg = f'merge request passed invalid individuals: {individuals}'
            AuditLog.backend_fault(log, msg, self)
            raise ValueError(msg)
        if not parameters:
            parameters = {}
        parameters['checksum'] = Individual.merge_request_hash([self] + individuals)
        delta = timedelta(days=Individual.get_merge_request_deadline_days())
        # allow us to override deadline delta; mostly good for testing
        if 'deadline_delta_seconds' in parameters and isinstance(
            parameters['deadline_delta_seconds'], int
        ):
            delta = timedelta(seconds=parameters['deadline_delta_seconds'])
        deadline = datetime.utcnow() + delta
        individual_guids = [str(indiv.guid) for indiv in individuals]
        args = (str(self.guid), individual_guids, parameters)
        async_res = execute_merge_request.apply_async(args, eta=deadline)
        AuditLog.audit_log_object(
            log,
            self,
            f'merge request from={individuals} queued up job {async_res} due {deadline}',
        )
        return {
            'individual': self,
            'deadline': deadline,
            'async': async_res,
            'id': async_res.id,
        }

    @classmethod
    def get_merge_request_data(cls, task_id):
        from app.utils import get_celery_data

        async_res, data = get_celery_data(task_id)
        if data and 'revoked' in data:
            log.info(f'get_merge_request_data(): id={task_id} has been revoked')
            return None
        if not async_res or not data:
            log.debug(f'get_merge_request_data(): id={task_id} unknown')
            return None
        if (
            'request' not in data
            or data['request'].get('name')
            != 'app.modules.individuals.tasks.execute_merge_request'
        ):
            log.warning(
                f'get_merge_request_data(): id={task_id} invalid name/data: {data}'
            )
            return None
        return data

    @classmethod
    def get_merge_request_stakeholders(cls, individuals):
        users = set()
        for indiv in individuals:
            for enc in indiv.encounters:
                if enc.get_owner():
                    users.add(enc.get_owner())
        return users

    # likely will evolve to include other reasons to not be allowed to merge (changes since request etc)
    @classmethod
    def validate_merge_request(
        cls, target_individual_guid, from_individual_ids, parameters=None
    ):
        all_individuals = []
        target_individual = Individual.query.get(target_individual_guid)
        if not target_individual:
            log.warning(
                f'validate_merge_request failed target individual {target_individual_guid}'
            )
            return False
        all_individuals.append(target_individual)
        for fid in from_individual_ids:
            findiv = Individual.query.get(fid)
            if not findiv:
                log.warning(f'validate_merge_request failed individual {fid}')
                return False
            all_individuals.append(findiv)
        if len(all_individuals) < 2:
            log.warning(
                f'validate_merge_request not enough individuals: {all_individuals}'
            )
            return False
        hash_start = None
        if parameters:
            hash_start = parameters.get('checksum')
        if not hash_start:
            log.warning('validate_merge_request does NOT have hash_start; oops!')
        else:
            hash_now = Individual.merge_request_hash(all_individuals)
            if hash_now != hash_start:
                log.warning(
                    f'validate_merge_request hash mismatch {hash_start} != {hash_now}'
                )
                return False
        return all_individuals

    def _merge_request_hash(self):
        parts = [enc._merge_request_hash() for enc in self.encounters]
        parts.append(hash(self.guid))
        parts.sort()
        return hash(tuple(parts))

    @classmethod
    def merge_request_hash(cls, individuals):
        parts = [indiv._merge_request_hash() for indiv in individuals]
        parts.sort()
        return hash(tuple(parts))

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
