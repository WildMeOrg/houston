# -*- coding: utf-8 -*-
"""
Individuals database models
--------------------
"""

import datetime
import logging
import uuid

from flask import current_app, url_for

import app.extensions.logging as AuditLog
from app.extensions import CustomFieldMixin, HoustonModel, db
from app.modules.names.models import DEFAULT_NAME_CONTEXT, Name
from app.utils import HoustonException

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
        db.DateTime,
        index=True,
        default=datetime.datetime.utcnow,
        nullable=False,
        primary_key=True,
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

    @classmethod
    def resolve_sent_notifications(cls, request_id):
        """
        Called when merge requests are approved/denied, this ensures any notifications sent about the request will be set to is_resolved=True
        """
        from app.modules.notifications.models import Notification, NotificationType

        # mildly expensive query and iterating through sub-dict, OK because this doesn't happen often.
        with db.session.begin(subtransactions=True):
            unresolved_merge_req_notif_guids = (
                db.session.query(Notification.guid)
                .filter(
                    Notification.message_type == NotificationType.individual_merge_request
                )
                .filter(Notification.is_resolved == False)  # noqa
            )
            unresolved_merge_req_notifs = [
                Notification.query.get(guid) for guid in unresolved_merge_req_notif_guids
            ]
            this_req_notifs = [
                notif
                for notif in unresolved_merge_req_notifs
                if notif.message_values
                and notif.message_values.get('request_id') == str(request_id)
            ]
            for notification in this_req_notifs:
                notification.is_resolved = True
                db.session.merge(notification)


class Individual(db.Model, HoustonModel, CustomFieldMixin):
    """
    Individuals database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    featured_asset_guid = db.Column(db.GUID, default=None, nullable=True)

    encounters = db.relationship(
        'Encounter', back_populates='individual', order_by='Encounter.guid'
    )

    names = db.relationship('Name', back_populates='individual', order_by='Name.created')

    comments = db.Column(db.String(), nullable=True)
    sex = db.Column(db.String(length=40), nullable=True)

    time_of_birth = db.Column(db.DateTime, index=True, default=None, nullable=True)
    time_of_death = db.Column(db.DateTime, index=True, default=None, nullable=True)

    # Matches guid in site.species
    # FIXME there will be a follow-up task to cdx-7 which makes this nullable=False ... later
    taxonomy_guid = db.Column(db.GUID, index=True, nullable=True)

    custom_fields = db.Column(db.JSON, default=lambda: {}, nullable=True)

    # social_groups = db.relationship(
    #     'SocialGroupIndividualMembership',
    #     back_populates='individual',
    #     order_by='SocialGroupIndividualMembership.individual_guid',
    # )

    # there is a backref'd 'relationship_memberships' list of RelationshipIndividualMember accessible here
    def user_is_owner(self, user):
        return user is not None and user in self.get_owners()

    @property
    def relationships(self):
        from app.modules.relationships.models import (
            Relationship,
            RelationshipIndividualMember,
        )

        return Relationship.query.join(Relationship.individual_members).filter(
            RelationshipIndividualMember.individual == self
        )

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.individuals.schemas import ElasticsearchIndividualSchema

        return ElasticsearchIndividualSchema

    # this ensures these mapping field/type values get into the Elasticsearch mapping for Individual
    #   as these may not have values on the first object index and therefore not be auto-mapped
    @classmethod
    def patch_elasticsearch_mappings(cls, mappings):
        mappings = super(Individual, cls).patch_elasticsearch_mappings(mappings)

        # ensures these get added only at top-level
        if '_schema' in mappings:
            mappings['death'] = {'type': 'date'}
            mappings['birth'] = {'type': 'date'}
            mappings['names'] = {
                'fields': {'keyword': {'ignore_above': 256, 'type': 'keyword'}},
                'type': 'text',
            }
            mappings['firstName'] = {'type': 'keyword'}
            mappings['comments'] = {'type': 'text'}

        if 'customFields' in mappings:
            mappings['customFields'] = cls.custom_field_elasticsearch_mappings(
                mappings['customFields']
            )

        if 'namesWithContexts' in mappings:
            for context in mappings['namesWithContexts']['properties']:
                mappings['namesWithContexts']['properties'][context] = {'type': 'keyword'}
        return mappings

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def run_integrity(cls):
        result = {'no_encounters': []}

        # Individuals without encounters are an error that should never really happen
        no_encounters = Individual.query.filter(~Individual.encounters.any()).all()
        if no_encounters:
            result['no_encounters'] = [ind.guid for ind in no_encounters]

        return result

    @classmethod
    def remove_all_empty(cls):
        # Individual without encounters are an error that should never really happen
        for indiv in Individual.query.filter(~Individual.encounters.any()).all():
            indiv.delete()

    def get_sex(self):
        return self.sex

    def get_time_of_birth(self):
        return self.time_of_birth

    def get_time_of_death(self):
        return self.time_of_death

    def get_comments(self):
        return self.comments

    def get_custom_fields(self):
        return self.custom_fields

    def get_taxonomy_guid(self):
        return self.taxonomy_guid

    def get_taxonomy_guid_inherit_encounters(self, sighting_fallback=True):
        tx_guid = self.taxonomy_guid
        if tx_guid is None:
            for encounter in self.encounters:
                tx_guid = encounter.get_taxonomy_guid(sighting_fallback)
                if tx_guid:
                    break
        return tx_guid

    # convenience method for frontend, display, search schema. Note the default inherit_encounters behavior.
    def get_taxonomy_names(self, inherit_encounters=True):
        if inherit_encounters:
            taxonomy_guid = self.get_taxonomy_guid_inherit_encounters()
        else:
            taxonomy_guid = self.taxonomy_guid
        if not taxonomy_guid:
            return None

        from app.modules.site_settings.models import Taxonomy

        # will raise ValueError if no good, but snh  :)
        tx = Taxonomy(taxonomy_guid)
        return tx.get_all_names()

    def get_taxonomy_object(self):
        tx_guid = self.get_taxonomy_guid()
        if not tx_guid:
            return None
        from app.modules.site_settings.models import Taxonomy

        tx = None
        try:
            tx = Taxonomy(tx_guid)
        except Exception:
            pass
        return tx

    # commented out for now due to duplication introduced by method above
    # def get_taxonomy_names(self):
    #    tx = self.get_taxonomy_object()
    #    if not tx:
    #        return []
    #    return tx.get_all_names()

    def get_name_values(self):
        name_vals = [name.value_resolved for name in self.names]
        return name_vals

    def get_names_with_contexts(self):
        return {name.context: name.value_resolved for name in self.names}

    def get_first_name(self):
        first_name = None
        for name in self.names:
            if name.context == 'FirstName':
                first_name = name.value
                break
        return first_name

    def get_first_name_keyword(self):
        from app.extensions.elasticsearch import MAX_UNICODE_CODE_POINT_CHAR

        first_name = self.get_first_name()
        if first_name is None:
            first_name = MAX_UNICODE_CODE_POINT_CHAR
        first_name_keyword = first_name.strip().lower()
        return first_name_keyword

    @classmethod
    def get_by_name(cls, name_value, context=DEFAULT_NAME_CONTEXT):
        matching_names = Name.query.filter(
            Name.value == name_value, Name.context == context
        )
        individuals = [name.individual for name in list(matching_names)]
        if len(individuals) > 1:
            raise HoustonException(
                log,
                f'Multiple individuals have name {name_value} in context {context}. Offending individuals: {[ind.guid for ind in individuals]}]',
            )
        individual = None
        if len(individuals) > 0:
            individual = individuals[0]
        return individual

    def get_adoption_name(self):
        adoption_name = None
        for name in self.names:
            if name.context == 'AdoptionName':
                adoption_name = name.value
                break
        return adoption_name

    def get_encounters(self):
        return self.encounters

    def get_encounter_guids(self):
        return [encounter.guid for encounter in self.encounters]

    def num_encounters(self):
        return len(self.encounters)

    def add_encounters(self, encounters):
        for encounter in encounters:
            if encounter not in self.get_encounters():
                self.encounters.append(encounter)

    def add_encounter(self, encounter):
        self.add_encounters([encounter])

    def remove_encounter(self, encounter):
        if encounter in self.get_encounters():
            self.encounters.remove(encounter)

    def get_sightings(self):
        sightings = set()  # force unique
        for enc in self.encounters:
            sightings.add(enc.sighting)
        return sightings

    def get_number_sightings(self):
        return len(self.get_sightings())

    def get_owners(self):
        return [encounter.owner for encounter in self.encounters]

    def get_names(self):
        return self.names

    def get_primary_name(self):
        if self.names and self.has_default_name():
            primary_name = self.get_name_for_context(DEFAULT_NAME_CONTEXT)
        elif self.names:
            ordered_names = sorted(self.names, key=lambda name: name.created)
            primary_name = ordered_names[0].value
        else:
            # should never happen, but seems like the desired behavior if it does in eg a
            # test where we haven't set names or rendering FE on weirdly-migrated data
            primary_name = str(self.guid)
        return primary_name

    def has_name_context(self, context):
        contexts = {name.context for name in self.names}
        return context in contexts

    def has_default_name(self):
        self.has_name_context(DEFAULT_NAME_CONTEXT)

    def has_name(self, name):
        for nm in self.names:
            if str(nm.guid) == str(name.guid):
                return True
        return False

    # should be only one of these
    def get_name_for_context(self, context):
        return Name.query.filter_by(individual_guid=self.guid, context=context).first()

    # can be many
    def get_names_for_value(self, value):
        return Name.query.filter_by(individual_guid=self.guid, value=value).all()

    def add_name(self, context, value, creator, preferring_users=[]):
        new_name = Name(
            individual_guid=self.guid,
            context=context,
            value=value,
            creator_guid=creator.guid if hasattr(creator, 'guid') else creator,
        )
        with db.session.begin(subtransactions=True):
            db.session.add(new_name)
        new_name.add_preferring_users(preferring_users)
        return new_name

    def remove_name(self, name):
        if self.guid != name.individual_guid:
            raise ValueError(f'{name} not on {self}')
        name.delete()

    def remove_name_for_context(self, context):
        name = self.get_name_for_context(context)
        if not name:
            return False
        name.delete()
        return True

    def remove_names_for_value(self, value):
        names = self.get_names_for_value(value)
        if not names:
            return 0
        num = len(names)
        for name in names:
            name.delete()
        return num

    # can update on only one type if desired
    def update_autogen_names(self, user, agn_type=None):
        from app.modules.autogenerated_names.models import AutogeneratedName

        if agn_type:
            autogen_names = AutogeneratedName.query.filter_by(type=agn_type).all()
        else:
            autogen_names = AutogeneratedName.query.all()
        if not autogen_names or not len(autogen_names):
            return
        for agn in autogen_names:
            self.update_autogen_name(user, agn)

    def update_autogen_name(self, user, agn):
        from app.modules.autogenerated_names.models import AutogeneratedNameType

        if not agn.enabled:
            return
        if agn.type == AutogeneratedNameType.auto_species.value:
            self.set_autogenerated_name_species(agn, user)
        else:
            # future development
            log.warning(f'skipping unsupported AutogeneratedName type={agn.type}')

    def set_autogenerated_name_species(self, agn, user):
        from app.modules.autogenerated_names.models import AutogeneratedNameType

        if not agn or agn.type != AutogeneratedNameType.auto_species.value:
            return
        tx_guid = self.get_taxonomy_guid()
        tx_guid = str(tx_guid) if tx_guid else None
        # now we iterate over names and: (a) remove any invalid-species AGN; (b) note if we have applicable-species AGN
        found = False
        remove = []
        for name in self.names:
            n_agn = name.get_autogenerated_name()
            if not n_agn:
                continue
            if str(n_agn.reference_guid) == tx_guid:
                found = name
            elif n_agn.type == AutogeneratedNameType.auto_species.value:
                # invalide taxonomy, so we gotta kill
                remove.append(name)
        for name in remove:
            log.debug(f'removing {name} from {self} due to {agn}')
            self.remove_name(name)
        # if we already have the name we need, or cannot use this agn, we bail
        if found or not tx_guid or str(tx_guid) != str(agn.reference_guid):
            log.debug(f'bailing due to found={found}, tx_guid={tx_guid}, agn={agn}')
            return
        new_name = agn.get_next()
        self.add_name(agn.context, new_name, user)

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

    def get_last_seen_time(self):
        last_enc = None
        for enc in self.encounters:
            if last_enc:
                # comparing ComplexDateTime values can throw exception; if so, we ignore
                try:
                    if enc.get_time() > last_enc.get_time():
                        last_enc = enc
                except Exception:
                    pass
            else:
                last_enc = enc

        # last_enc == None is BAD here, but we handle it just in case
        return last_enc.get_time() if last_enc else None

    def get_last_seen_time_isoformat(self):
        lstime = self.get_last_seen_time()
        return lstime.isoformat_in_timezone() if lstime else None

    def get_last_seen_time_specificity(self):
        lstime = self.get_last_seen_time()
        return lstime.specificity if lstime else None

    def has_annotations(self):
        for enc in self.encounters:
            if enc.annotations and len(enc.annotations) > 0:
                return True
        return False

    def get_featured_image_url(self):
        featured_image_url = None
        featured_asset_guid = self.get_featured_asset_guid()
        if featured_asset_guid:
            # FIXME Does this route exist?
            featured_image_url = (
                url_for(
                    'api.annotations_annotation_by_id',
                    annotation_guid=str(featured_asset_guid),
                    _external=True,
                )
                + '/image'
            )
        return featured_image_url

    # returns Individuals
    def get_cooccurring_individuals(self):
        return Individual.get_multiple(self.get_cooccurring_individual_guids())

    # returns guids
    def get_cooccurring_individual_guids(self):
        return Individual.get_cooccurring_individual_guids_for_individual_guid(self.guid)

    # arbitrary individual_guid
    @classmethod
    def get_cooccurring_individual_guids_for_individual_guid(cls, individual_guid):
        from sqlalchemy.orm import aliased

        from app.modules.encounters.models import Encounter
        from app.modules.sightings.models import Sighting

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
        from sqlalchemy.orm import aliased

        from app.modules.encounters.models import Encounter
        from app.modules.sightings.models import Sighting

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
            return True
        else:
            return False

    def _ensure_asset_individual_association(self, asset_guid):

        rt_val = False
        from app.modules.assets.models import Asset

        asset = Asset.find(asset_guid)
        if asset and asset.annotations:
            for annotation in asset.annotations:
                if annotation.encounter.individual_guid == self.guid:
                    rt_val = True
        return rt_val

    # note: since encounters are only re-assigned, no cascade problems happen around merging
    def merge_from(self, *source_individuals, parameters=None):
        if (
            not source_individuals
            or not isinstance(source_individuals, tuple)
            or len(source_individuals) < 1
        ):
            raise ValueError('must be passed a tuple of at least 1 individual')
        data = {
            'targetIndividualId': str(self.guid),
            'sourceIndividualIds': [],
            'parameters': parameters,
        }
        for indiv in source_individuals:
            # we verify that we dont have self-individual in here, which turns out to be "bad"
            if indiv.guid == self.guid:
                raise ValueError(f'attempt to merge individual {indiv.guid} with self')
            data['sourceIndividualIds'].append(str(indiv.guid))

        # this replicates what edm used to return
        rtn = {'targetId': str(self.guid), 'merged': {}}

        # mvp dictates that *target* individual dictates sex and name, unless parameters.override indicate otherwise
        if parameters and parameters.get('override') and 'sex' in parameters['override']:
            self.sex = parameters['override']['sex']
        rtn['targetSex'] = self.sex

        from app.modules.site_settings.models import Taxonomy

        # cdx-8 behavior will mimic above but for taxonomy, except we *require* to have something
        if (
            parameters
            and parameters.get('override')
            and 'taxonomy_guid' in parameters['override']
        ):
            self.taxonomy_guid = parameters['override']['taxonomy_guid']
        if not self.taxonomy_guid:
            raise ValueError('target individual must have a taxonomy set')
        Taxonomy(self.taxonomy_guid)  # will raise ValueError if bad
        rtn['targetTaxonomyGuid'] = self.taxonomy_guid

        # notably, self.taxonomy_guid has already been set (as merge_names() uses it)
        self.merge_names(
            source_individuals,
            parameters
            and parameters.get('override')
            and parameters['override'].get('name_context'),
        )
        # now we steal their encounters and delete them
        # NOTE:  technically we could iterate over the enc ids in merged.merged_id array, but we run (tiny) risk of this individual
        #   getting assigned to additional encounters in the interim, so instead we just steal all the encounters directly
        for indiv in source_individuals:
            rtn['merged'][
                str(indiv.guid)
            ] = []  # list of encounters that were moved from this source_indiv
            for enc in indiv.encounters:
                AuditLog.audit_log_object(
                    log, indiv, f'merge assigning our {enc} to {self}'
                )
                AuditLog.audit_log_object(
                    log, self, f'assigned {enc} from merged {indiv}'
                )
                enc.individual_guid = self.guid
                rtn['merged'][str(indiv.guid)].append(str(enc.guid))
            self._consolidate_social_groups(indiv)
            indiv.delete()
        AuditLog.audit_log_object(
            log,
            self,
            f"merge SUCCESS from {data['sourceIndividualIds']}",
        )
        return rtn

    # mimics individual.merge_from(), but does not immediately executes; rather waits for approval
    #   and initiates a request including time-out etc
    # - really likely only useful via api endpoint (based on permissions); not direct call
    # - just a light wrapper to _merge_request_init()
    def merge_request_from(self, source_individuals, parameters=None):
        res = self._merge_request_init(source_individuals, parameters)
        Individual.merge_notify([self] + source_individuals, res)
        return res

    # note: for merge_complete individuals will only contain target individual, but
    #   request_data should contain key from_individual_ids
    @classmethod
    def merge_notify(cls, individuals, request_data, notif_type=None):
        from flask_login import current_user

        from app.modules.notifications.models import NotificationType

        if not notif_type:
            notif_type = NotificationType.individual_merge_request
        # Use method to get real stakeholders (public isn't one)
        stakeholders = cls.get_merge_request_stakeholders(individuals)

        # Build up dict of which individuals each user is a stakeholder for
        owner_individuals = {}
        for indiv in individuals:
            for enc in indiv.encounters:
                if enc.owner not in owner_individuals:
                    owner_individuals[enc.owner] = []
                owner_individuals[enc.owner].append(indiv)
        log.debug(
            f'merge_notify() type={notif_type} created owners structure {owner_individuals}'
        )

        for stakeholder in stakeholders:
            # we only skip current_user when it is merge_request (merge_complete/block goes to all users)
            if (
                notif_type == NotificationType.individual_merge_request
                and stakeholder == current_user
            ):
                continue

            Individual._merge_notify_user(
                current_user,
                stakeholder,
                owner_individuals[stakeholder],
                individuals,
                request_data,
                notif_type,
            )

    @classmethod
    def _merge_notify_user(
        cls, sender, user, your_individuals, all_individuals, request_data, notif_type
    ):
        from app.modules.notifications.models import Notification, NotificationBuilder

        other_individuals = []
        for indiv_id in range(len(all_individuals)):
            if all_individuals[indiv_id] not in your_individuals:
                other_individuals.append(all_individuals[indiv_id])

        builder = NotificationBuilder(sender)
        builder.set_individual_merge(your_individuals, other_individuals, request_data)
        notification = Notification.create(notif_type, user, builder)
        log_msg = f'merge request: notification {notification} from {sender} re: {your_individuals}'
        AuditLog.audit_log_object(log, user, log_msg)

    @classmethod
    def merge_request_cancel_task(cls, req_id):
        current_app.celery.control.revoke(req_id)
        Individual.merge_request_cleanup(req_id)

    # scrubs notifications etc, once a merge has completed
    @classmethod
    def merge_request_cleanup(cls, req_id):
        IndividualMergeRequestVote.resolve_sent_notifications(req_id)
        log.debug(
            f'[{req_id}] merge_request_cleanup (notifications, etc) not yet fully implemented'
        )

    @classmethod
    def merge_request_celery_task(
        cls, cel_task, target_individual_guid, from_individual_ids, parameters
    ):
        from app.modules.notifications.models import NotificationType

        log_id = f'<execute_merge_request {cel_task.request.id}>'
        log.info(
            f'{log_id} initiated for Individual {target_individual_guid} (from {from_individual_ids}; {parameters})'
        )
        all_individuals = Individual.validate_merge_request(
            target_individual_guid, from_individual_ids, parameters
        )
        if not all_individuals:
            msg = f'{log_id} failed validation'
            AuditLog.houston_fault(log, msg)
            return

        # validate_merge_request should check hashes etc and means we are good to merge
        target_individual = all_individuals.pop(0)
        try:
            res = target_individual.merge_from(*all_individuals, parameters=parameters)
        except Exception as ex:
            res = f'Exception caught: {str(ex)}'
        if not isinstance(res, dict):
            msg = f'{log_id} (via celery task) merge_from failed: {res}'
            AuditLog.houston_fault(log, msg)
            return

        log.info(f'{log_id} merge completed, results={res}')

        # notify users that merge has happened
        #   NOTE request_data here may need some altering depending on what final templates look like
        #   also unclear who *sender* will be, so that may need to be passed
        request_data = {
            'id': cel_task.request.id,
            'from_individual_ids': from_individual_ids,
            'merge_outcome': 'deadline',
        }
        Individual.merge_notify(
            [target_individual] + all_individuals,
            request_data,
            NotificationType.individual_merge_complete,
        )

    # note: this will destructively remove names from source_individuals
    #  override looks like:  { context: value } and will replace any/all names with context
    #    in the case of autogen names, value will be name-guid
    #  currently, override-context will only replace an existing one, not add to names when it does not exist
    #  NOTE: self.taxonomy_guid should be set (as result of merge) prior to this, as we need it here
    #  NOTE 2: taxonomy may have changed since initial request, so need to be thorough here (not trust initial validation)
    def merge_names(self, source_individuals, override=None, fail_on_conflict=False):
        self._merge_names_simple(source_individuals, override, fail_on_conflict)
        self._merge_names_agn(source_individuals, override, fail_on_conflict)

    def _merge_names_simple(
        self, source_individuals, override=None, fail_on_conflict=False
    ):
        from app.modules.autogenerated_names.models import AUTOGEN_NAME_CONTEXT_PREFIX

        override_contexts = set()
        if isinstance(override, dict):
            for ctx in override.keys():
                if not ctx.startswith(AUTOGEN_NAME_CONTEXT_PREFIX):
                    override_contexts.add(ctx)
        contexts_on_self = set()
        for name in self.names:
            if not name.autogenerated_guid:
                contexts_on_self.add(name.context)
        for indiv in source_individuals:
            for name in indiv.names:
                if name.autogenerated_guid:
                    continue
                elif fail_on_conflict and name.context in contexts_on_self:
                    raise ValueError(f'conflict on context {name.context} on {indiv}')
                elif (
                    name.context in override_contexts and name.context in contexts_on_self
                ):
                    continue  # skip, as override will ultimately win
                elif name.context in contexts_on_self:
                    name.context = Individual._incremented_context(
                        name.context, contexts_on_self
                    )
                name.individual_guid = self.guid  # attach name to self
                contexts_on_self.add(name.context)
        # now we deal with overrides
        for name in self.names:
            if name.context in override_contexts:
                name.value = override[name.context]
        db.session.refresh(self)  # updates .names on all parties

    def _merge_names_agn(self, source_individuals, override=None, fail_on_conflict=False):
        from app.modules.autogenerated_names.models import (
            AUTOGEN_NAME_CONTEXT_PREFIX,
            AutogeneratedNameType,
        )
        from app.modules.names.models import Name

        override_contexts = set()
        if isinstance(override, dict):
            for ctx in override.keys():
                if ctx.startswith(AUTOGEN_NAME_CONTEXT_PREFIX):
                    override_contexts.add(ctx)
        names_on_self = set()
        contexts_on_self = set()
        for name in self.names:
            if name.autogenerated_guid:
                names_on_self.add(name)
            else:
                contexts_on_self.add(name.context)
        log.debug(
            f'_merge_names_agn({self}) => override_contexts={override_contexts} names_on_self={names_on_self} contexts_on_self={contexts_on_self}'
        )

        # now for AGN - we need to really consider the _type_ here - we only want one of each and we need to make
        #   sure that the one we are choosing is "applicable" (e.g. not wrong taxonomy)
        use_for_type = {}
        needs_historical = []
        # override should win, so do first
        for ctx in override_contexts:
            name = Name.query.get(override[ctx])
            if not name:  # ugh i dunno...
                if fail_on_conflict:
                    raise ValueError(f'invalid name guid at {ctx} in override {override}')
                else:
                    continue
            type = str(name.get_autogenerated_name().type.value)
            if type in use_for_type:
                # probably shouldnt happen that > 1 type in override... but...
                if name != use_for_type[type]:
                    needs_historical.append(name)
            else:
                use_for_type[type] = name
        # now non-override (from self only)
        for name in names_on_self:
            type = str(name.get_autogenerated_name().type.value)
            if type in use_for_type:
                if name != use_for_type[type]:
                    needs_historical.append(name)
            else:
                use_for_type[type] = name
        # non-override for source_individuals: only for historical (cannot be used for type, unless via override)
        for indiv in source_individuals:
            for name in indiv.names:
                if not name.autogenerated_guid:
                    continue
                type = str(name.get_autogenerated_name().type.value)
                if type in use_for_type and use_for_type[type] != name:
                    # not used via override
                    needs_historical.append(name)
        # check that taxonomy matches (we may not have, which means agn not enabled for taxonomy)
        tx_name = (
            str(AutogeneratedNameType.auto_species.value) in use_for_type
            and use_for_type[str(AutogeneratedNameType.auto_species.value)]
        )
        if tx_name and (
            str(tx_name.get_autogenerated_name().reference_guid)
            != str(self.taxonomy_guid)
        ):
            raise ValueError(
                f'wanting to use {use_for_type[AutogeneratedNameType.auto_species.value].get_autogenerated_name()} but does not match individual.taxonomy {self.taxonomy_guid}'
            )
        log.debug(
            f'_merge_names_agn({self}) => use_for_type={use_for_type} needs_historical={needs_historical}'
        )
        for use in use_for_type.values():
            if not self.has_name(use):
                # we have to remove previous that uses this
                self.remove_name_for_context(use.context)
                self.names.append(use)
        hist_context_base = 'Historical Codex ID'
        hist_context = hist_context_base
        for name in needs_historical:
            if hist_context in contexts_on_self:
                hist_context = Individual._incremented_context(
                    hist_context_base, contexts_on_self
                )
            log.debug(
                f'historical trying {name} with contexts_on_self={contexts_on_self} hist_context=>{hist_context}'
            )
            contexts_on_self.add(hist_context)
            self.add_name(
                hist_context,
                f'{name.get_autogenerated_name().prefix}-{name.value}',
                name.creator_guid,
            )
            if self.has_name(name):
                self.remove_name(name)
        db.session.refresh(self)  # updates .names on all parties
        return self.names

    @classmethod
    def _incremented_context(cls, ctx, existing):
        import re

        num = -1
        reg = '^' + ctx + r'(\d+)'
        for ex in existing:
            if ex == ctx and num < 0:
                # ctx "should always" be in existing, so this is "guaranteed"
                num = 0
                continue
            m = re.match(reg, ex)
            if not m:
                continue
            val = int(m.groups()[0])
            num = max(val, num)
        if num < 0:
            # this means our guarantee failed
            raise ValueError(f'no matches of {ctx} in {existing}')
        num += 1
        return f'{ctx}{num}'

    def get_blocking_encounters(self):
        blocking = []
        for enc in self.encounters:
            if not enc.current_user_has_edit_permission() and not enc.is_public():
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

    @classmethod
    def get_merge_request_deadline_days(cls):
        from app.modules.site_settings.models import SiteSetting

        return SiteSetting.get_value('individualMergeDefaultDelayDays')

    # does the actual work of setting up celery task to execute this merge
    # NOTE: this does not do any notification of users; see merge_request_from()
    def _merge_request_init(self, individuals, parameters=None):
        from app.modules.individuals.tasks import execute_merge_request
        from app.modules.site_settings.models import Taxonomy

        if not individuals or not isinstance(individuals, list) or len(individuals) < 1:
            msg = f'merge request passed invalid individuals: {individuals}'
            AuditLog.frontend_fault(log, msg, self)
            raise ValueError(msg)
        for indiv in individuals:
            if indiv.guid == self.guid:
                msg = f'attempt to merge individual {indiv.guid} with self'
                AuditLog.frontend_fault(log, msg, self)
                raise ValueError(msg)
        if not parameters:
            parameters = {}

        # cdx-8 requires us to have a taxonomy (via target/self or override)
        try_tx = self.taxonomy_guid
        if parameters.get('override') and 'taxonomy_guid' in parameters['override']:
            try_tx = parameters['override']['taxonomy_guid']
        if not try_tx:
            raise ValueError(
                'target individual must have a taxonomy set or override value'
            )
        Taxonomy(try_tx)  # will raise ValueError if bad

        parameters['checksum'] = Individual.merge_request_hash([self] + individuals)
        delta = datetime.timedelta(days=Individual.get_merge_request_deadline_days())
        # allow us to override deadline delta; mostly good for testing
        if 'deadline_delta_seconds' in parameters and isinstance(
            parameters['deadline_delta_seconds'], int
        ):
            delta = datetime.timedelta(seconds=parameters['deadline_delta_seconds'])
        deadline = datetime.datetime.utcnow() + delta
        individual_guids = [str(indiv.guid) for indiv in individuals]
        stakeholders = Individual.get_merge_request_stakeholders([self] + individuals)
        parameters['stakeholder_guids'] = [str(u.guid) for u in stakeholders]
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
                enc_owner = enc.get_owner()
                if enc_owner and not enc_owner.is_internal:
                    users.add(enc_owner)
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
        parts = [enc.merge_request_hash() for enc in self.encounters]
        parts.append(hash(self.guid))
        parts.sort()
        return hash(tuple(parts))

    @classmethod
    def get_active_merge_requests(cls, user=None):
        from app.utils import get_celery_tasks_scheduled

        try:
            reqs = get_celery_tasks_scheduled(
                'app.modules.individuals.tasks.execute_merge_request'
            )
        except NotImplementedError:
            AuditLog.backend_fault(log, 'celery failure')
            return []

        if not user:
            return reqs
        user_reqs = []
        for req in reqs:
            if (  # warning, extreme nested json parsing!
                'request' in req
                and 'args' in req['request']
                and isinstance(req['request']['args'], list)
                and len(req['request']['args']) > 2
                and isinstance(req['request']['args'][2], dict)
                and 'stakeholder_guids' in req['request']['args'][2]
                and isinstance(req['request']['args'][2]['stakeholder_guids'], list)
                and str(user.guid) in req['request']['args'][2]['stakeholder_guids']
            ):
                user_reqs.append(req)
        return user_reqs

    @classmethod
    def merge_request_hash(cls, individuals):
        parts = [indiv._merge_request_hash() for indiv in individuals]
        parts.sort()
        return hash(tuple(parts))

    @classmethod
    def find_merge_conflicts(self, individuals):
        if len(individuals) < 2:
            raise ValueError('not enough individuals')
        values = {'sex': set(), 'taxonomy_guid': set()}
        name_contexts = {}
        for individual in individuals:
            for name in individual.names:
                name_contexts[name.context] = name_contexts.get(name.context, 0) + 1
            values['sex'].add(individual.get_sex())
            values['taxonomy_guid'].add(individual.get_taxonomy_guid())
        conflicts = {'name_contexts': []}
        for key in values.keys():
            if len(values[key]) > 1:
                conflicts[key] = True
        for context in name_contexts.keys():
            if name_contexts[context] > 1:
                conflicts['name_contexts'].append(context)
        if not conflicts['name_contexts']:
            del conflicts['name_contexts']  # eject if empty
        return conflicts

    def delete(self):
        AuditLog.delete_object(log, self)
        for name in self.names:
            name.delete()
        with db.session.begin(subtransactions=True):
            while self.social_groups:
                db.session.delete(self.social_groups.pop())

            if self.relationship_memberships:
                for relationship_membership in self.relationship_memberships:
                    relationship_membership.delete()

            db.session.delete(self)

    def get_social_groups_json(self):
        from app.modules.social_groups.schemas import DetailedSocialGroupSchema

        social_groups = {
            soc_group_memship.social_group for soc_group_memship in self.social_groups
        }
        social_group_schema = DetailedSocialGroupSchema()
        social_groups = [
            social_group_schema.dump(social_group).data for social_group in social_groups
        ]
        return social_groups

    def get_social_groups_elasticsearch(self):
        from app.modules.social_groups.models import SocialGroup

        social_groups = {
            soc_group_memship.social_group for soc_group_memship in self.social_groups
        }
        es = []
        for sg in social_groups:
            mem = sg.get_member(str(self.guid))
            role_names = []
            for role_guid in mem.roles:
                role_data = SocialGroup.get_role_data(role_guid)
                role_names.append(role_data.get('label'))
            es.append(
                {
                    'guid': str(sg.guid),
                    'name': sg.name,
                    'role_guids': mem.roles,
                    'role_names': role_names,
                }
            )
        return es

    def get_relationships_elasticsearch(self):
        rels = []
        for mem in self.relationship_memberships:
            rel = mem.relationship
            rels.append(
                {
                    'guid': str(rel.guid),
                    'type_guid': str(rel.type_guid),
                    'type_label': rel.type_label,
                    'role_label': mem.individual_role_label,
                    'role_guid': str(mem.individual_role_guid),
                    'other_individual_guid': str(rel.other_individual(self.guid).guid),
                }
            )
        return rels
