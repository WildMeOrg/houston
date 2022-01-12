# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""
import enum
import logging
import uuid
import json
from datetime import datetime  # NOQA
from flask import current_app

from app.extensions import FeatherModel, HoustonModel, db, is_extension_enabled
from app.modules.annotations.models import Annotation
from app.modules.encounters.models import Encounter
from app.modules.individuals.models import Individual
from app.utils import HoustonException
import app.extensions.logging as AuditLog

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SightingAssets(db.Model, HoustonModel):
    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    sighting_guid = db.Column(db.GUID, db.ForeignKey('sighting.guid'), primary_key=True)
    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)
    sighting = db.relationship('Sighting', back_populates='sighting_assets')
    asset = db.relationship(
        'Asset',
        backref=db.backref(
            'asset_sightings',
            primaryjoin='Asset.guid == SightingAssets.asset_guid',
            order_by='SightingAssets.sighting_guid',
            cascade='delete, delete-orphan',
        ),
    )


class SightingStage(str, enum.Enum):
    identification = 'identification'
    un_reviewed = 'un_reviewed'
    processed = 'processed'
    failed = 'failed'


class Sighting(db.Model, FeatherModel):
    """
    Sightings database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    sighting_assets = db.relationship('SightingAssets')
    stage = db.Column(
        db.Enum(SightingStage),
        nullable=False,
    )
    featured_asset_guid = db.Column(db.GUID, default=None, nullable=True)

    # May have multiple jobs outstanding, store as Json obj dictionary, uuid_str is key,
    # Content = {'algorithm': model, 'active': Bool}
    jobs = db.Column(db.JSON, default=lambda: {}, nullable=True)

    asset_group_sighting_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group_sighting.guid'),
        index=True,
        nullable=True,
    )
    asset_group_sighting = db.relationship(
        'AssetGroupSighting', back_populates='sighting', uselist=False
    )

    name = db.Column(db.String(length=120), nullable=True)

    time_guid = db.Column(
        db.GUID, db.ForeignKey('complex_date_time.guid'), index=True, nullable=False
    )
    time = db.relationship('ComplexDateTime')

    encounters = db.relationship(
        'Encounter', back_populates='sighting', order_by='Encounter.guid'
    )
    unreviewed_start = db.Column(
        db.DateTime, index=True, default=datetime.utcnow, nullable=False
    )
    review_time = db.Column(
        db.DateTime, index=True, default=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'stage={self.stage}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def get_matching_set_options(cls):
        # If you extend this, update the method below that uses them
        return ['mine', 'extended', 'all']

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

    def get_creator(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting.get_owner()
        else:
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

    def user_is_owner(self, user):
        return user in self.get_owners()

    def get_encounters(self):
        return self.encounters

    def add_encounter(self, encounter):
        if encounter not in self.encounters:
            self.encounters.append(encounter)

    def get_time_isoformat_in_timezone(self):
        return self.time.isoformat_in_timezone() if self.time else None

    def get_time_specificity(self):
        return self.time.specificity if self.time else None

    # this does the heavy lifting of trying to set time from user-provided data
    def set_time_from_data(self, data):
        if not data or 'time' not in data:
            return  # no need to try, time not being set
        from app.modules.complex_date_time.models import ComplexDateTime

        # will raise ValueError if data no good
        self.time = ComplexDateTime.from_data(data)

    def get_assets(self):
        return [ref.asset for ref in self.sighting_assets]

    def add_asset(self, asset):
        if asset not in self.get_assets():
            with db.session.begin(subtransactions=True):
                self.add_asset_in_context(asset)

    def add_assets(self, asset_list):
        with db.session.begin():
            for asset in asset_list:
                self.add_asset_in_context(asset)

    def add_asset_in_context(self, asset):
        rel = SightingAssets(sighting=self, asset=asset)
        db.session.add(rel)
        self.sighting_assets.append(rel)
        if self.featured_asset_guid is None:
            self.featured_asset_guid = asset.guid

    def add_asset_no_context(self, asset):
        rel = SightingAssets(sighting_guid=self.guid, asset_guid=asset.guid)
        self.sighting_assets.append(rel)
        if self.featured_asset_guid is None:
            self.featured_asset_guid = asset.guid

    def add_assets_no_context(self, asset_list):
        for asset in asset_list:
            self.add_asset_no_context(asset)

    def get_featured_asset_guid(self):
        asset_guids = [
            sighting_asset.asset_guid for sighting_asset in self.sighting_assets
        ]
        rtn_val = None
        if self.featured_asset_guid not in asset_guids:
            self.featured_asset_guid = None
        if self.featured_asset_guid is not None:
            rtn_val = self.featured_asset_guid
        elif asset_guids:
            rtn_val = asset_guids[0]
        return rtn_val

    def set_featured_asset_guid(self, guid):
        asset_guids = [
            sighting_asset.asset_guid for sighting_asset in self.sighting_assets
        ]
        if guid in asset_guids:
            self.featured_asset_guid = guid

    def get_detection_start_time(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting.get_detection_start_time()
        return None

    def get_curation_start_time(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting.get_curation_start_time()
        return None

    # Don't store identification start time directly. It's either the creation time if we ever had identification
    # jobs or None if no identification was done (and hence no jobs exist)
    def get_identification_start_time(self):
        if len(self.jobs) > 0:
            return self.created.isoformat() + 'Z'
        return None

    # unreviewed start time is only valid if there were no active identification jobs
    def get_unreviewed_start_time(self):
        if not self.any_jobs_active():
            return self.unreviewed_start.isoformat() + 'Z'
        return None

    def get_review_time(self):
        if self.stage == SightingStage.processed:
            return self.review_time.isoformat() + 'Z'
        else:
            return None

    @classmethod
    def check_jobs(cls):
        for sighting in Sighting.query.all():
            sighting.check_all_job_status()

    def check_all_job_status(self):
        jobs = self.jobs
        if not jobs:
            return
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                current_app.acm.request_passthrough_result(
                    'job.response', 'post', {}, job
                )
                # TODO Process response DEX-335
                # TODO If UTC Start more than {arbitrary limit} ago.... do something

    @classmethod
    def print_jobs(cls):
        for sighting in Sighting.query.all():
            sighting.print_active_jobs()

    def print_active_jobs(self):
        for job_id in self.jobs.keys():
            job = self.jobs[job_id]
            if job['active']:
                log.warning(
                    f"Sighting:{self.guid} Job:{job_id} Matching_set:{job['matching_set']} "
                    f"Algorithm:{job['algorithm']} Annotation:{job['annotation']} UTC Start:{job['start']}"
                )

    def any_jobs_active(self):
        jobs = self.jobs
        if not jobs:
            return False
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                return True
        return False

    # Build up dict to print out status (calling function chooses what to collect and print)
    def get_job_details(self, annotation_id, verbose):

        details = {}
        for job_id in self.jobs.keys():
            if annotation_id == self.jobs[job_id]['annotation']:
                details[job_id] = self.jobs[job_id]
                if verbose:
                    details[job_id]['request'] = self.build_identification_request(
                        self.jobs[job_id]['matching_set'],
                        self.jobs[job_id]['annotation'],
                        job_id,
                        self.jobs[job_id]['algorithm'],
                    )
                    details[job_id][
                        'response'
                    ] = current_app.acm.request_passthrough_result(
                        'job.response', 'post', {}, job_id
                    )

        return details

    def delete(self):
        AuditLog.delete_object(log, self)
        while self.sighting_assets:
            db.session.delete(self.sighting_assets.pop())
        with db.session.begin():
            db.session.delete(self)

    def delete_cascade(self):
        assets = self.get_assets()
        with db.session.begin(subtransactions=True):
            while self.sighting_assets:
                # this is actually removing the SightingAssets joining object (not the assets)
                db.session.delete(self.sighting_assets.pop())
            while self.encounters:
                enc = self.encounters.pop()
                enc.delete_cascade()
            AuditLog.delete_object(log, self)
            db.session.delete(self)
            while assets:
                asset = assets.pop()
                asset.delete()

    def delete_from_edm(self, current_app, request):
        return Sighting.delete_from_edm_by_guid(current_app, self.guid, request)

    def delete_from_edm_and_houston(self, request=None):
        # first try delete on edm, deleting all sub components too
        class DummyRequest(object):
            def __init__(self, headers):
                self.headers = headers

        if not request:
            request = DummyRequest(
                headers={
                    'x-allow-delete-cascade-individual': 'True',
                    'x-allow-delete-cascade-sighting': 'True',
                }
            )

        try:
            (response, response_data, result) = self.delete_from_edm(current_app, request)
        except HoustonException as ex:
            if (
                ex.get_val('edm_status_code', 0) == 404
                or ex.get_val('edm_status_code', 0) == 500
            ):
                # assume that means that we tried to delete a non-existent sighting
                # TODO handle failure
                self.delete_cascade()
                AuditLog.audit_log_object(
                    log,
                    self,
                    f'deleted of {self.guid} on EDM failed, assuming it was not there',
                )
                return
            raise

        deleted_individuals = None
        deleted_ids = []
        if result and isinstance(result, dict):
            deleted_individuals = result.get('deletedIndividuals', None)
        if deleted_individuals:
            from app.modules.individuals.models import Individual

            deleted_ids = []
            for indiv_guid in deleted_individuals:
                goner = Individual.query.get(indiv_guid)
                if goner is None:
                    log.error(
                        f'EDM requested cascade-delete of individual id={indiv_guid}; but was not found in houston!'
                    )
                else:
                    log.info(f'EDM requested cascade-delete of {goner}; deleting')
                    deleted_ids.append(indiv_guid)
                    goner.delete()
        # if we get here, edm has deleted the sighting, now houston feather
        # TODO handle failure of feather deletion (when edm successful!)  out-of-sync = bad
        self.delete_cascade()

        return deleted_ids

    @classmethod
    def delete_from_edm_by_guid(cls, current_app, guid, request):
        assert guid is not None
        return current_app.edm.request_passthrough_parsed(
            'sighting.data',
            'delete',
            {},
            guid,
            request_headers=request.headers,
        )

    def get_jobs_json(self):
        job_data = []
        for job in self.jobs:
            from app.modules.sightings.schemas import DetailedSightingJobSchema

            schema = DetailedSightingJobSchema()
            this_job = schema.dump(self.jobs[job]).data
            this_job['job_id'] = job
            job_data.append(this_job)

        return job_data

    def get_debug_sighting_json(self):
        response = current_app.edm.get_dict('sighting.data_complete', self.guid)
        if not isinstance(response, dict):  # some non-200 thing, incl 404
            return response
        if not response.get('success', False):
            return response

        from app.modules.sightings.schemas import DebugSightingSchema

        schema = DebugSightingSchema()
        edm_response = response['result']
        for encounter in edm_response.get('encounters') or []:
            # EDM returns strings for decimalLatitude and decimalLongitude
            if encounter.get('decimalLongitude'):
                encounter['decimalLongitude'] = float(encounter['decimalLongitude'])
            if encounter.get('decimalLatitude'):
                encounter['decimalLatitude'] = float(encounter['decimalLatitude'])
            encounter['guid'] = encounter.pop('id', None)
        edm_response.update(schema.dump(self).data)
        edm_response.pop('id', None)
        return self._augment_edm_json(edm_response)

    def get_augmented_sighting_json(self):
        if is_extension_enabled('edm'):
            response = current_app.edm.get_dict('sighting.data_complete', self.guid)
        if not isinstance(response, dict):  # some non-200 thing, incl 404
            return response
        if not response.get('success', False):
            return response

        from app.modules.sightings.schemas import AugmentedEdmSightingSchema

        schema = AugmentedEdmSightingSchema()
        edm_response = response['result']
        for encounter in edm_response.get('encounters') or []:
            # EDM returns strings for decimalLatitude and decimalLongitude
            if encounter.get('decimalLongitude'):
                encounter['decimalLongitude'] = float(encounter['decimalLongitude'])
            if encounter.get('decimalLatitude'):
                encounter['decimalLatitude'] = float(encounter['decimalLatitude'])
            encounter['guid'] = encounter.pop('id', None)
        edm_response.update(schema.dump(self).data)
        edm_response.pop('id', None)

        return self._augment_edm_json(edm_response)

    # given edm_json (verbose json from edm) will populate with houston-specific data from feather object
    # note: this modifies the passed in edm_json, so not sure how legit that is?
    def _augment_edm_json(self, edm_json):

        if (self.encounters is not None and edm_json['encounters'] is None) or (
            self.encounters is None and edm_json['encounters'] is not None
        ):
            log.warning('Only one None encounters value between edm/feather objects!')
        if self.encounters is not None and edm_json['encounters'] is not None:
            id_to_encounter = {e['guid']: e for e in edm_json['encounters']}
            if set(str(e.guid) for e in self.encounters) != set(id_to_encounter):
                log.warning(
                    'Imbalanced encounters between edm/feather objects on sighting '
                    + str(self.guid)
                    + '!'
                )
                raise ValueError('imbalanced encounter count between edm/feather')

            from app.modules.encounters.schemas import AugmentedEdmEncounterSchema

            for encounter in self.encounters:  # now we augment each encounter
                found_edm = id_to_encounter[str(encounter.guid)]
                edm_schema = AugmentedEdmEncounterSchema(exclude=('annotations',))
                found_edm.update(edm_schema.dump(encounter).data)

        return edm_json

    # pass results-json for sighting.encounters from changes made (e.g. PATCH) and update houston encounters accordingly
    def rectify_edm_encounters(self, edm_encs_json, user=None):
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
            log.debug(f'adding new houston Encounter guid={enc_id}')
            user_guid = user.guid if user else None
            encounter = Encounter(
                guid=enc_id,
                asset_group_sighting_encounter_guid=uuid.uuid4(),
                version=edm_map[enc_id].get('version', 3),
                owner_guid=user_guid,
                submitter_guid=user_guid,
            )
            self.add_encounter(encounter)

    def _get_matching_set_annots(self, matching_set_option):
        annots = []

        # Must match the options validated in the metadata.py
        if matching_set_option == 'mine':
            data_owner = self.single_encounter_owner()
            assert data_owner
            annots = data_owner.get_my_annotations()
        elif matching_set_option == 'extended':
            data_owner = self.single_encounter_owner()
            assert data_owner
            annots = data_owner.get_all_annotations()
        elif matching_set_option == 'all':
            annots = Annotation.query.all()
        else:
            # Should have been caught at the metadata validation
            log.error(f'MatchingDataSet {matching_set_option} not supported')

        unique_annots = set(annots)
        return unique_annots

    def get_matching_set_data(self, matching_set_option):
        from app.extensions.acm import to_acm_uuid

        unique_annots = self._get_matching_set_annots(matching_set_option)
        matching_set_individual_uuids = []
        matching_set_annot_uuids = []
        for annot in unique_annots:
            if annot.encounter:
                if annot.encounter.sighting.stage == SightingStage.processed:
                    acm_annot_uuid = to_acm_uuid(annot.content_guid)
                    if acm_annot_uuid not in matching_set_annot_uuids:
                        matching_set_annot_uuids.append(acm_annot_uuid)
                        individual = annot.get_individual()
                        if individual:
                            individual_guid = str(individual.guid)
                        else:
                            # Use Sage default value
                            individual_guid = '____'
                        matching_set_individual_uuids.append(individual_guid)

        log.debug(
            f'Built matching set individuals {matching_set_individual_uuids}, '
            f'annots {matching_set_annot_uuids}'
        )
        return matching_set_individual_uuids, matching_set_annot_uuids

    def _has_matching_set(self, matching_set_option):
        unique_annots = self._get_matching_set_annots(matching_set_option)
        for annot in unique_annots:
            if annot.encounter:
                if annot.encounter.sighting.stage == SightingStage.processed:
                    return True
        return False

    def build_identification_request(
        self, config_id, annotation_uuid, job_uuid, algorithm
    ):
        (
            matching_set_individual_uuids,
            matching_set_annot_uuids,
        ) = self.get_matching_set_data(config_id)

        assert len(matching_set_individual_uuids) == len(matching_set_annot_uuids)

        # Sage doesn't support an empty database set, so if no annotations, don't send the request
        if len(matching_set_individual_uuids) == 0:
            return {}

        from app.extensions.acm import to_acm_uuid

        base_url = current_app.config.get('BASE_URL')
        from app.modules.ia_config_reader import IaConfig

        callback_url = (
            f'{base_url}api/v1/sightings/{str(self.guid)}/sage_identified/{str(job_uuid)}'
        )
        ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))
        try:
            id_config_dict = ia_config_reader.get(f'_identifiers.{algorithm}')['sage']
        except KeyError:
            raise HoustonException(log, f'failed to find {algorithm}')

        id_request = {
            'jobid': str(job_uuid),
            'callback_url': f'houston+{callback_url}',
            'callback_detailed': True,
            'matching_state_list': [],
            'query_annot_name_list': ['____'],
            'query_annot_uuid_list': [
                to_acm_uuid(annotation_uuid),
            ],
            'database_annot_name_list': matching_set_individual_uuids,
            'database_annot_uuid_list': matching_set_annot_uuids,
        }
        id_request = id_request | id_config_dict

        log.debug(f'sending message to sage :{id_request}')
        return id_request

    def send_identification(
        self, config_id, algorithm_id, annotation_uuid, annotation_sage_uuid
    ):
        from datetime import datetime

        log.debug(
            f'In send_identification for cnf:{config_id}  algo:{algorithm_id}  Ann UUID:{annotation_uuid}'
        )
        id_configs = self.asset_group_sighting.get_id_configs()
        # Message construction has to be in the task as the jobId must be unique
        job_uuid = uuid.uuid4()
        matching_set_data = id_configs[config_id].get('matchingSetDataOwners')
        algorithm = id_configs[config_id]['algorithms'][algorithm_id]
        id_request = self.build_identification_request(
            matching_set_data, annotation_sage_uuid, job_uuid, algorithm
        )
        if id_request != {}:
            encoded_request = {}
            for key in id_request:
                encoded_request[key] = json.dumps(id_request[key])
            try:
                current_app.acm.request_passthrough_result(
                    'job.identification_request', 'post', {'params': encoded_request}
                )

                log.info(f'Sent ID Request, creating job {job_uuid}')
                self.jobs[str(job_uuid)] = {
                    'matching_set': matching_set_data,
                    'algorithm': algorithm,
                    'annotation': str(annotation_uuid),
                    'active': True,
                    'start': datetime.utcnow(),
                }
                # This is necessary because we can only mark self as modified if
                # we assign to one of the database attributes
                self.jobs = self.jobs
                with db.session.begin(subtransactions=True):
                    db.session.merge(self)
            except HoustonException:
                log.warning(
                    f'Sage Identification on Sighting({self.guid}) Job{job_uuid} failed to start'
                )
                # TODO Celery will retry, do we want it to?
                self.stage = SightingStage.failed

        else:
            # TODO, this is correct for MVP as there is only one id per Sighting but this will need
            # rework when there are multiple
            self.stage = SightingStage.un_reviewed

    # validate that the id response is a valid format and extract the data required from it
    def _parse_id_response(self, job_id_str, data):
        status = data.get('status', 'failed')

        if status != 'completed':
            self.stage = SightingStage.failed
            # This is not an exception as the message from Sage was valid
            error_msg = f'JobID {job_id_str} failed  message: {status}'
            AuditLog.backend_fault(log, error_msg, self)
            return

        job_id_msg = data.get('jobid')
        if not job_id_msg:
            raise HoustonException(log, f'Must be a job id in the response {job_id_str}')

        if job_id_msg != job_id_str:
            raise HoustonException(
                log,
                f'Job id in message {job_id_msg} must match job id in callback {job_id_str}',
            )
        json_result = data.get('json_result')
        if not json_result:
            raise HoustonException(
                log, f'No json_result in the response for {job_id_str}'
            )

        query_annot_uuids = json_result.get('query_annot_uuid_list', [])
        if not query_annot_uuids:
            raise HoustonException(
                log, f'No query_annot_uuid_list in the json_result for {job_id_str}'
            )

        if len(query_annot_uuids) != 1:
            raise HoustonException(
                log,
                f'Sage ID responded with {len(query_annot_uuids)} query_annots for {job_id_str}',
            )
        from app.modules.annotations.models import Annotation
        from app.extensions.acm import from_acm_uuid

        acm_uuid = from_acm_uuid(query_annot_uuids[0])
        query_annots = Annotation.query.filter_by(content_guid=acm_uuid).all()
        if not query_annots:
            raise HoustonException(
                log,
                f'Sage ID response with unknown query annot uuid {acm_uuid} for job {job_id_str}',
            )

        possible_annot_guids = [str(annot.guid) for annot in query_annots]
        job = self.jobs[job_id_str]
        if job['annotation'] not in possible_annot_guids:
            raise HoustonException(
                log,
                f'Sage ID response with invalid annot uuid {acm_uuid} for job {job_id_str}',
            )

        # Now it's reasonably valid, let's extract the bits we need
        result = {
            'scores_by_annotation': [],
            'scores_by_individual': [],
        }
        for target_annot_data in json_result['summary_annot']:
            acm_uuid = from_acm_uuid(target_annot_data['duuid'])
            target_annot = Annotation.query.filter_by(content_guid=acm_uuid).first()
            if not target_annot:
                raise HoustonException(
                    log,
                    f'Sage ID response with unknown target annot uuid {acm_uuid} for job {job_id_str}',
                )
            result['scores_by_annotation'].append(
                {str(target_annot.guid): target_annot_data['score']}
            )

        for target_annot_data in json_result['summary_name']:
            acm_uuid = from_acm_uuid(target_annot_data['duuid'])
            target_annot = Annotation.query.filter_by(content_guid=acm_uuid).first()
            if not target_annot:
                raise HoustonException(
                    log,
                    f'Sage ID response with unknown target annot uuid {acm_uuid} for job {job_id_str}',
                )
            result['scores_by_individual'].append(
                {str(target_annot.guid): target_annot_data['score']}
            )

        return result

    def identified(self, job_id, data):
        if self.stage != SightingStage.identification:
            raise HoustonException(log, f'Sighting {self.guid} is not detecting')
        job_id_str = str(job_id)
        if job_id_str not in self.jobs:
            raise HoustonException(log, f'job_id {job_id_str} not found')

        result = self._parse_id_response(job_id_str, data)

        from app.modules.ia_config_reader import IaConfig

        ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))
        job = self.jobs[job_id_str]
        algorithm = job['algorithm']
        try:
            id_config_dict = ia_config_reader.get(f'_identifiers.{algorithm}')
        except KeyError:
            raise HoustonException(log, f'failed to find {algorithm}')

        assert id_config_dict
        description = ''
        frontend_data = id_config_dict.get('frontend', '')
        if frontend_data:
            description = frontend_data.get('description', '')
        log.info(
            f"Received successful {self.guid} {algorithm} response '{description}' from Sage for {job_id_str}"
        )
        log.debug(f'Sighting ID response stored result: {result}')

        # All good, mark as complete
        job['active'] = False
        job['result'] = result
        job['complete_time'] = datetime.utcnow()

        self.jobs = self.jobs
        self.stage = SightingStage.un_reviewed
        self.unreviewed_start = datetime.utcnow()
        with db.session.begin(subtransactions=True):
            db.session.merge(self)

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll ACM to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True

    # Helper to build the annotation score data from the job result
    def _get_annotation_id_data_from_job(self, t_annot_result, q_annot_job):

        data = {}
        assert len(t_annot_result.keys()) == 1
        t_annot_guid = list(t_annot_result.keys())[0]
        t_annot = Annotation.query.get(t_annot_guid)
        # If no annot, assume that annot has been deleted since the job was run and use None
        if t_annot:
            data = {
                'guid': t_annot_guid,
                'score': t_annot_result[t_annot_guid],
                'id_finish_time': str(q_annot_job['complete_time']),
            }

        return t_annot, data

    # Helper to ensure that the required annot and individual data is present
    def _ensure_annot_data_in_response(self, annot, response):

        individual_guid = annot.encounter.individual_guid if annot.encounter else None

        if annot.guid not in response['annotation_data'].keys():
            encounter_location = (
                annot.encounter.get_location() if annot.encounter else None
            )
            # add annot data
            response['annotation_data'][str(annot.guid)] = {
                'viewpoint': annot.viewpoint,
                'encounter_location': encounter_location,
                'individual_guid': individual_guid,
                'image_url': annot.get_image_url(),
            }

        if (
            individual_guid is not None
            and annot.encounter.individual_guid not in response['individual_data'].keys()
        ):
            individual = Individual.query.get(individual_guid)
            assert individual
            # add individual data
            response['individual_data'][str(individual_guid)] = {
                'names': individual.get_names(),
                'last_seen': str(individual.get_last_seen_time()),
                'image': individual.get_featured_image_url(),
            }

    # See https://docs.google.com/document/d/1oveaPLspQsXS7XXx3hxKA8HUCYb2p-A2wd4zGPga3rs/edit#
    def get_id_result(self):

        response = {
            'query_annotations': [],
            'annotation_data': {},
            'individual_data': {},
        }
        query_annots = []
        for enc in self.encounters:
            query_annots += enc.annotations

        for q_annot in query_annots:
            response['query_annotations'].append(
                {
                    'guid': str(q_annot.guid),
                    'status': 'not_run',
                    'individual_guid': None,
                    'algorithms': {},
                }
            )
            if q_annot.encounter and q_annot.encounter.individual_guid is not None:
                response['query_annotations'][-1][
                    'individual_guid'
                ] = q_annot.encounter.individual_guid
            self._ensure_annot_data_in_response(q_annot, response)

            q_annot_jobs = [
                self.jobs[job]
                for job in self.jobs
                if self.jobs[job]['annotation'] == str(q_annot.guid)
            ]
            if len(q_annot_jobs) < 1:
                # Not run is perfectly valid
                continue

            q_annot_job = q_annot_jobs[-1]
            if q_annot_job['active']:
                response['query_annotations'][-1]['status'] = 'pending'
                continue

            # It's valid, extract the data
            response['query_annotations'][-1]['status'] = 'complete'

            scores_by_annot = []
            scores_by_individual = []
            for t_annot_result in q_annot_job['result']['scores_by_annotation']:
                t_annot, data = self._get_annotation_id_data_from_job(
                    t_annot_result, q_annot_job
                )

                if not t_annot:
                    # Assume that annot has been deleted since the job was run
                    continue

                scores_by_annot.append(data)
                self._ensure_annot_data_in_response(t_annot, response)

            for t_annot_result in q_annot_job['result']['scores_by_individual']:
                t_annot, data = self._get_annotation_id_data_from_job(
                    t_annot_result, q_annot_job
                )

                if not t_annot:
                    # Assume that annot has been deleted since the job was run
                    continue

                scores_by_individual.append(data)
                self._ensure_annot_data_in_response(t_annot, response)

            algorithms = {
                q_annot_job['algorithm']: {
                    'scores_by_annotation': scores_by_annot,
                    'scores_by_individual': scores_by_individual,
                }
            }

            response['query_annotations'][-1]['algorithms'] = algorithms
            log.debug(f'Sighting ID response: {response}')
        return response

    # Returns a percentage complete value 0-100 for the AssetGroupSighting operations that occur withing
    # the Sighting object
    def get_completion(self):
        # Design allows for these limits to be configured later, potentially this data could be project specific
        stage_base_sizes = {
            SightingStage.identification: 0,
            SightingStage.un_reviewed: 66,  # 2/3 of the time in sighting ia pipeline is in identification
            SightingStage.processed: 100,  # The rest is spent being reviewed
            SightingStage.failed: 100,  # complete, even if failed
        }
        completion = stage_base_sizes[self.stage]

        # virtually all stages are either all or nothing, these just use the base sizes above.
        # For those that have granularity we need to know the size range available and estimate how much has been done
        if self.stage == SightingStage.identification:
            if len(self.jobs) > 0:
                size_range = (
                    stage_base_sizes[SightingStage.identification]
                    - stage_base_sizes[self.stage]
                )
                complete_jobs = [job for job in self.jobs.values() if not job['active']]
                completion += size_range * (len(complete_jobs) / len(self.jobs))
        return completion

    def ia_pipeline(self):
        from .tasks import send_identification

        assert self.stage == SightingStage.identification
        num_algorithms = 0
        id_configs = self.asset_group_sighting.get_id_configs()
        num_configs = len(id_configs)
        if num_configs > 0:
            # Only one for MVP
            assert num_configs == 1
            for config_num in range(num_configs):
                config = id_configs[config_num]
                assert 'algorithms' in config
                # Only one for MVP
                assert len(config['algorithms']) == 1
                assert 'matchingSetDataOwners' in config

                # Only use the algorithm if there is a matching data set to ID against
                if self._has_matching_set(config['matchingSetDataOwners']):
                    num_algorithms += len(config['algorithms'])

                # For now, regions are ignored

        encounters_with_annotations = [
            encounter for encounter in self.encounters if len(encounter.annotations) != 0
        ]

        # No annotations to identify or no algorithms, go straight to un-reviewed
        if len(encounters_with_annotations) == 0 or num_algorithms == 0:
            self.stage = SightingStage.un_reviewed
            log.info(
                f'Sighting {self.guid} un-reviewed, {num_algorithms} algoirithms, '
                f'{len(encounters_with_annotations)} encounters with annotations'
            )
            for encounter in self.encounters:
                encounter_metadata = self.asset_group_sighting.get_encounter_metadata(
                    encounter.asset_group_sighting_encounter_guid
                )
                if encounter_metadata:
                    if 'individualUuid' in encounter_metadata:
                        individual = Individual.query.get(
                            uuid.UUID(encounter_metadata['individualUuid'])
                        )
                        assert individual
                        encounter.set_individual(individual)
        else:
            num_jobs = 0
            # Use task to send ID req with retries
            # Once we support multiple IA configs and algorithms, the number of jobs is going to grow....rapidly
            for config_id in range(len(id_configs)):
                for algorithm_id in range(len(id_configs[config_id]['algorithms'])):
                    for encounter in self.encounters:
                        for annotation in encounter.annotations:
                            log.debug(
                                f'Sending ID for Sighting:{self.guid}, config:{config_id}, algo:{algorithm_id}'
                                f'annot:{annotation.guid}, sage_annot:{annotation.content_guid}'
                            )
                            send_identification.delay(
                                str(self.guid),
                                config_id,
                                algorithm_id,
                                annotation.guid,
                                annotation.content_guid,
                            )
                            num_jobs += 1
            log.info(
                f'Starting Identification for Sighting:{self.guid} using {num_jobs} jobs'
            )
