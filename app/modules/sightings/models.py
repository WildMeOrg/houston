# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""
import enum
import logging
import uuid
import json

from flask import current_app

from app.extensions import FeatherModel, HoustonModel, db
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
    asset = db.relationship('Asset', back_populates='asset_sightings')


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

    encounters = db.relationship(
        'Encounter', back_populates='sighting', order_by='Encounter.guid'
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
                    f"Algorithm:{job['algorithm']} Annotation:{job['annotaion']} UTC Start:{job['start']}"
                )

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
            id_config_dict = ia_config_reader.get(f'_identifiers.{algorithm}').copy()
        except KeyError:
            raise HoustonException(log, f'failed to find {algorithm}')

        # description is used for populating the frontend but Sage complains if it's there so remove it
        id_config_dict.pop('description', None)
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

    def identified(self, job_id, data):
        if self.stage != SightingStage.identification:
            raise HoustonException(log, f'Sighting {self.guid} is not detecting')
        job_id_str = str(job_id)
        if job_id_str not in self.jobs:
            raise HoustonException(log, f'job_id {job_id} not found')
        job = self.jobs[job_id_str]

        if not job['active']:
            raise HoustonException(log, f'job_id {job_id} not active')

        status = data.get('status')
        if not status:
            raise HoustonException(
                log, f'No status in ID response from Sage {job_id_str}'
            )

        success = status.get('success', False)
        if not success:
            self.stage = SightingStage.failed
            # This is not an exception as the message from Sage was valid
            code = status.get('code', 'unset')
            message = status.get('message', 'unset')
            error_msg = f'JobID {job_id_str} failed with code: {code} message: {message}'
            AuditLog.backend_fault(log, error_msg, self)
            return

        response = data.get('response')
        if not response:
            raise HoustonException(
                log, f'No response field in message from Sage {job_id_str}'
            )

        job_id_msg = response.get('jobid')
        if not job_id_msg:
            raise HoustonException(log, f'Must be a job id in the response {job_id_str}')

        if job_id_msg != job_id_str:
            raise HoustonException(
                log,
                f'Job id in message {job_id_msg} must match job id in callback {job_id_str}',
            )
        json_result = response.get('json_result')
        if not json_result:
            raise HoustonException(
                log, f'No json_result in the response for {job_id_str}'
            )

        cm_dict = json_result.get('cm_dict')
        if not cm_dict:
            raise HoustonException(log, f'No cm_dict in the json_result for {job_id_str}')

        query_config_dict = json_result.get('query_config_dict')
        if not query_config_dict:
            raise HoustonException(
                log, f'No query_config_dict in the json_result for {job_id_str}'
            )

        query_annot_uuids = json_result.get('query_annot_uuid_list', [])
        if not query_annot_uuids:
            raise HoustonException(
                log, f'No query_annot_uuid_list in the json_result for {job_id_str}'
            )

        from app.modules.ia_config_reader import IaConfig

        ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))

        algorithm = job['algorithm']
        try:
            id_config_dict = ia_config_reader.get(f'_identifiers.{algorithm}')
        except KeyError:
            raise HoustonException(log, f'failed to find {algorithm}')

        assert id_config_dict
        description = id_config_dict.get('description', '')
        log.info(
            f"Received successful {algorithm} response '{description}' from Sage for {job_id_str}"
        )

        # All good, mark as complete
        job['active'] = False
        self.jobs = self.jobs
        self.stage = SightingStage.un_reviewed

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll ACM to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True

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
                complete_jobs = [job for job in self.jobs if not job['active']]
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
            for config in id_configs:
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
                            send_identification.delay(
                                str(self.guid),
                                config_id,
                                algorithm_id,
                                annotation.guid,
                                annotation.content_guid,
                            )
                            num_jobs += 1
            log.info(f'Starting Identification for {self.guid} using {num_jobs} jobs')
