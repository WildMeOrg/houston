# -*- coding: utf-8 -*-
"""
AssetGroups database models
--------------------
"""
import copy
import enum
from flask import current_app, url_for
from flask_login import current_user  # NOQA
from datetime import datetime  # NOQA
from flask_restx_patched._http import HTTPStatus
from app.extensions import db, HoustonModel
import app.extensions.logging as AuditLog  # NOQA
from app.extensions.acm import from_acm_uuid
from app.extensions.git_store import GitStore
from app.modules.annotations.models import Annotation
from app.modules.assets.models import Asset
from app.modules.encounters.models import Encounter
from app.modules.individuals.models import Individual
from app.modules.names.models import DEFAULT_NAME_CONTEXT
from app.modules.sightings.models import Sighting, SightingStage
from app.modules.users.models import User
from app.utils import HoustonException

import logging
import uuid
import json

from .metadata import AssetGroupMetadata

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

MAX_DETECTION_ATTEMPTS = 10


class AssetGroupSightingStage(str, enum.Enum):
    unknown = 'unknown'
    preparation = 'preparation'
    detection = 'detection'
    curation = 'curation'
    processed = 'processed'
    failed = 'failed'


# AssetGroup can have many sightings, so needs a table
class AssetGroupSighting(db.Model, HoustonModel):

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    guid = db.Column(db.GUID, default=uuid.uuid4, primary_key=True)
    stage = db.Column(
        db.Enum(AssetGroupSightingStage),
        default=AssetGroupSightingStage.unknown,
        nullable=False,
    )
    asset_group_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group.guid'),
        index=True,
        nullable=False,
    )
    asset_group = db.relationship('AssetGroup', back_populates='asset_group_sightings')

    # configuration metadata from the create request
    config = db.Column(db.JSON, nullable=True)

    sighting = db.relationship('Sighting')

    # May have multiple jobs outstanding, store as Json obj uuid_str is key, In_progress Bool is value
    jobs = db.Column(db.JSON, default=lambda: {}, nullable=True)

    curation_start = db.Column(
        db.DateTime, index=True, default=datetime.utcnow, nullable=False
    )
    detection_attempts = db.Column(db.Integer, default=0, nullable=False)

    def user_is_owner(self, user: User) -> bool:
        # AssetGroupSighting has no owner, so uses the AssetGroup one
        return self.asset_group.user_is_owner(user)

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.asset_groups.schemas import BaseAssetGroupSightingSchema

        return BaseAssetGroupSightingSchema

    def __init__(self, asset_group, sighting_config, detection_configs):
        self.asset_group = asset_group
        self.config = {
            'sighting': sighting_config,
            'detections': detection_configs,
        }

        # Start by writing to DB so that all rollback on failure works
        with db.session.begin(subtransactions=True):
            db.session.add(self)
        db.session.refresh(self)

        self.set_stage(AssetGroupSightingStage.preparation, refresh=False)

        if (
            not asset_group.progress_preparation
            or asset_group.progress_preparation.complete
        ):
            self.post_preparation_hook()

        AuditLog.user_create_object(log, self)

    @property
    def sighting_config(self):
        return None if self.config is None else self.config.get('sighting', None)

    @sighting_config.setter
    def sighting_config(self, value):
        if self.config is None:
            self.config = {}
        self.config['sighting'] = value

    @property
    def detection_configs(self):
        return None if self.config is None else self.config.get('detections', None)

    @detection_configs.setter
    def detection_configs(self, value):
        if self.config is None:
            self.config = {}
        self.config['detections'] = value

    @property
    def progress_preparation(self):
        return self.asset_group.progress_preparation

    def post_preparation_hook(self):
        if self.stage != AssetGroupSightingStage.preparation:
            return

        assert (
            self.asset_group.progress_preparation is None
            or self.asset_group.progress_preparation.complete
        )

        # Allow sightings to have no Assets, they go straight to curation
        if (
            'assetReferences' not in self.sighting_config
            or len(self.sighting_config['assetReferences']) == 0
        ):
            self.set_stage(AssetGroupSightingStage.curation)
            self.commit()

        elif len(self.detection_configs) == 1 and (
            not self.detection_configs[0] or self.detection_configs[0] == 'None'
        ):
            self.set_stage(AssetGroupSightingStage.curation)
        else:
            self.set_stage(AssetGroupSightingStage.detection)

        if self.stage == AssetGroupSightingStage.detection:
            try:
                self.start_detection()

            except HoustonException as ex:
                self.delete()
                raise ex

    def commit(self):
        from app.modules.utils import Cleanup
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        if self.stage != AssetGroupSightingStage.curation:
            raise HoustonException(
                log,
                f'AssetGroupSighting {self.guid} is currently in {self.stage}, not curating cannot commit',
            )

        if not self.sighting_config:
            raise HoustonException(
                log,
                f'AssetGroupSighting {self.guid} has no metadata',
            )
        cleanup = Cleanup('AssetGroup')

        # Create sighting in EDM
        try:
            # Don't send the encounter guids. EDM doesn't use them but they confuse anyone reading logs
            sent_data = self.sighting_config
            for enc in sent_data['encounters']:
                enc.pop('guid')
            result_data = current_app.edm.request_passthrough_result(
                'sighting.data',
                'post',
                {'data': sent_data, 'headers': {'Content-Type': 'application/json'}},
                '',
            )
        except HoustonException as ex:
            cleanup.rollback_and_abort(
                ex.message,
                'Sighting.post failed',
                ex.status_code,
                ex.get_val('error', 'Error'),
            )

        cleanup.add_guid(result_data['id'], Sighting)

        # if we get here, edm has made the sighting.  now we have to consider encounters contained within,
        # and make houston for the sighting + encounters

        # encounters via self.sighting_config and edm (result_data) need to have same count!
        if ('encounters' in self.sighting_config and 'encounters' not in result_data) or (
            'encounters' not in self.sighting_config and 'encounters' in result_data
        ):
            cleanup.rollback_and_houston_exception(
                log,
                'Missing encounters between requested config and result',
                'Sighting.post missing encounters in one of %r or %r'
                % (self.sighting_config, result_data),
            )
        if not len(self.sighting_config['encounters']) == len(result_data['encounters']):
            cleanup.rollback_and_houston_exception(
                log,
                'Imbalance in encounters between data and result',
                'Sighting.post imbalanced encounters in %r or %r'
                % (self.sighting_config, result_data),
            )

        sighting = Sighting(
            guid=result_data['id'],
            # asset_group_sighting=self,  -- see note below
            name=self.sighting_config.get('name', ''),
            stage=SightingStage.identification,
            version=result_data.get('version', 2),
        )
        try:
            sighting.set_time_from_data(self.sighting_config)
        except ValueError as ve:
            cleanup.rollback_and_abort(
                f'Problem with sighting time/timeSpecificity values: {str(ve)}',
                f"invalid time ({self.sighting_config.get('time')}) or timeSpecificity ({self.sighting_config.get('timeSpecificity')}): {str(ve)}",
                error_fields=['time'],
            )
        if not sighting.time:
            cleanup.rollback_and_houston_exception(
                log,
                'Must have time/timeSpecificity values',
                'Must have time/timeSpecificity values',
            )

        with db.session.begin(subtransactions=True):
            db.session.add(sighting)

        # Add the assets for all of the encounters to the created sighting object
        for reference in self.sighting_config.get('assetReferences', []):
            asset = self.asset_group.get_asset_for_file(reference)
            assert asset
            sighting.add_asset(asset)

        cleanup.add_object(sighting)

        for encounter_num in range(len(self.sighting_config['encounters'])):
            req_data = self.sighting_config['encounters'][encounter_num]
            res_data = result_data['encounters'][encounter_num]
            try:
                owner_guid = self.asset_group.owner_guid
                if 'ownerEmail' in req_data:
                    owner_email = req_data['ownerEmail']
                    encounter_owner = User.find(email=owner_email)
                    # Validated in the metadata code so must be correct
                    assert encounter_owner
                    owner_guid = encounter_owner.guid

                individual = None
                if DEFAULT_NAME_CONTEXT in req_data:
                    individual = Individual.get_by_name(req_data[DEFAULT_NAME_CONTEXT])

                assert 'guid' in req_data
                new_encounter = Encounter(
                    guid=res_data['id'],
                    version=res_data.get('version', 2),
                    individual=individual,
                    owner_guid=owner_guid,
                    asset_group_sighting_encounter_guid=req_data['guid'],
                    submitter_guid=self.asset_group.submitter_guid,
                )
                new_encounter.set_time_from_data(req_data)

                AuditLog.user_create_object(log, new_encounter, f'for owner {owner_guid}')

                annotations = req_data.get('annotations', [])
                for annot_uuid in annotations:
                    annot = Annotation.query.get(annot_uuid)
                    assert annot

                    AuditLog.audit_log_object(
                        log,
                        new_encounter,
                        f' Added annotation {annot_uuid}',
                        AuditLog.AuditType.Update,
                    )

                    new_encounter.add_annotation(annot)

                sighting.add_encounter(new_encounter)
                with db.session.begin(subtransactions=True):
                    db.session.add(new_encounter)

            except Exception as ex:
                cleanup.rollback_and_houston_exception(
                    log,
                    f'Problem with creating encounter [{encounter_num}]: {ex}',
                    f'{ex} on encounter {encounter_num}: enc={req_data}',
                )

        # This has to be done as the final step in the creation as the FE does not seem to wait for the commit
        # response but starts using the sighting as soon as it can be read from the AGS
        sighting.set_asset_group_sighting(self)

        # AssetGroupSighting is finished, all subsequent processing is on the Sighting
        self.complete()
        sighting.ia_pipeline()

        num_encounters = len(self.sighting_config['encounters'])
        AuditLog.user_create_object(
            log, sighting, f'with {num_encounters} encounter(s)', duration=timer.elapsed()
        )

        return sighting

    def has_filename(self, filename):
        return (
            filename in self.sighting_config.get('assetReferences', [])
            if self.sighting_config
            else False
        )

    def has_annotation(self, annot_guid):
        ret_val = False
        if self.sighting_config and self.sighting_config['encounters']:
            for enc in self.sighting_config['encounters']:
                if annot_guid in enc.get('annotations', []):
                    ret_val = True
                    break
        return ret_val

    def get_owner(self):
        return self.asset_group.owner

    def get_sighting_guid(self):
        if len(self.sighting) > 0:
            return str(self.sighting[0].guid)
        else:
            return None

    # Don't store detection start time directly. It's either the creation time if we ever had detection
    # jobs or None if no detection was done (and hence no jobs exist)
    def get_detection_start_time(self):
        if self.jobs or self.stage == AssetGroupSightingStage.detection:
            return self.created.isoformat() + 'Z'
        return None

    # curation time is only valid if there are no active detection jobs and there were some assets
    # Either detection has completed or no detection jobs were run
    def get_curation_start_time(self):
        if (
            self.stage != AssetGroupSightingStage.detection
            and not self.any_jobs_active()
            and 'assetReferences' in self.sighting_config.keys()
            and len(self.sighting_config['assetReferences']) != 0
        ):
            return self.curation_start.isoformat() + 'Z'
        return None

    def get_detailed_jobs_json(self):
        job_data = []
        for job in self.jobs:
            from app.modules.asset_groups.schemas import (
                DetailedAssetGroupSightingJobSchema,
            )

            schema = DetailedAssetGroupSightingJobSchema()
            this_job = schema.dump(self.jobs[job]).data
            this_job['job_id'] = job
            job_data.append(this_job)

        return job_data

    def get_debug_jobs_json(self):
        job_data = []
        for job in self.jobs:
            from app.modules.asset_groups.schemas import DebugAssetGroupSightingJobSchema

            schema = DebugAssetGroupSightingJobSchema()
            this_job = schema.dump(self.jobs[job]).data
            this_job['job_id'] = job
            job_data.append(this_job)

        return job_data

    # returns a getter for a given config field, allowing for casting and default vals
    @staticmethod
    def config_field_getter(field_name, default=None, cast=None):
        def getter(self):
            value = self.get_config_field(field_name)

            if cast is not None and value:
                value = cast(value)
            return value or default

        return getter

    def get_config_field(self, field):
        value = (
            self.sighting_config.get(field)
            if isinstance(self.sighting_config, dict)
            else None
        )
        if not value:
            value = self.asset_group.get_config_field(field)
        return value

    def get_custom_fields(self):
        return self.__class__.config_field_getter('customFields', default={})(self)

    def _augment_encounter_json(self, encounter_data):
        from app.modules.users.schemas import PublicUserSchema
        from app.modules.annotations.schemas import BaseAnnotationSchema

        user_schema = PublicUserSchema()
        annot_schema = BaseAnnotationSchema()
        enc_json = copy.deepcopy(encounter_data)
        enc_json['createdHouston'] = self.created
        enc_json['updatedHouston'] = self.updated
        enc_json['annotations'] = []
        if 'annotations' in encounter_data.keys():
            enc_json['annotations'] = []
            for annot_guid in encounter_data['annotations']:
                annot_json = annot_schema.dump(Annotation.query.get(annot_guid)).data
                annot_json['encounter_guid'] = encounter_data['guid']
                enc_json['annotations'].append(annot_json)

        owner = self.asset_group.owner
        if 'ownerEmail' in encounter_data:
            owner = User.find(email=encounter_data['ownerEmail'])
            # Validated in the metadata code so must be correct
            assert owner
        enc_json['owner'] = user_schema.dump(owner).data
        if self.asset_group.submitter_guid:
            submitter = User.find(self.asset_group.submitter_guid)
            enc_json['submitter'] = user_schema.dump(submitter).data
        return enc_json

    def get_encounter_json(self, encounter_guid):
        encounters = self.sighting_config and self.sighting_config.get('encounters') or []
        enc_json = None
        for encounter in encounters:
            if encounter['guid'] == str(encounter_guid):
                enc_json = self._augment_encounter_json(encounter)
                break
        return enc_json

    def get_encounters_json(self):
        encounters = self.sighting_config and self.sighting_config.get('encounters') or []
        enc_json = []
        for encounter in encounters:
            enc_json.append(self._augment_encounter_json(encounter))

        return enc_json

    @classmethod
    def check_jobs(cls):
        # get scheduled celery tasks only once and use for all AGS
        from app.utils import get_celery_tasks_scheduled

        all_scheduled = get_celery_tasks_scheduled(
            'app.modules.asset_groups.tasks.sage_detection'
        )
        for asset_group_sighting in AssetGroupSighting.query.filter(
            AssetGroupSighting.stage == AssetGroupSightingStage.detection
        ).all():
            asset_group_sighting.check_all_job_status(all_scheduled)

    def check_all_job_status(self, all_scheduled):
        jobs = self.jobs
        if not jobs:
            if not all_scheduled:
                # TODO it would be nice to know if the scheduled tasks were for other AGS than this one
                # but at the moment, it's not clear how we could detect this
                log.warning(
                    f'{self.guid} is detecting but no detection jobs are running, '
                    'assuming Celery error and starting them again'
                )
            try:
                self.rerun_detection(background=False)
            except Exception:
                log.exception(f'{self} rerun_detection failed')
            return
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                current_app.acm.request_passthrough_result(
                    'job.response', 'post', {}, job_id
                )
                # TODO Process response
                # TODO If UTC Start more than {arbitrary limit} ago.... do something

    def any_jobs_active(self):
        jobs = self.jobs
        if not jobs:
            return False
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                return True
        return False

    @classmethod
    def get_all_jobs_debug(cls, verbose):
        jobs = []
        for asset_group_sighting in AssetGroupSighting.query.all():
            jobs.extend(asset_group_sighting.get_jobs_debug(verbose))
        return jobs

    def get_pipeline_status(self):
        db.session.refresh(self)
        status = {
            'preparation': self._get_pipeline_status_preparation(),
            'detection': self._get_pipeline_status_detection(),
            'identification': self._get_pipeline_status_identification(),
            'now': datetime.utcnow().isoformat(),
            'stage': self.stage,
            'migrated': False,  # always false, but just for consistency with sighting
            'summary': {
                'progress': None,
            },
        }
        status['summary']['complete'] = (
            status['preparation']['complete'] and status['detection']['complete']
        )
        steps_total = status['preparation']['steps'] + status['detection']['steps']
        steps_complete_total = (
            status['preparation']['stepsComplete'] + status['detection']['stepsComplete']
        )
        if steps_total:
            status['summary']['progress'] = steps_complete_total / steps_total
        return status

    # TODO just a placeholder now
    def _get_pipeline_status_preparation(self):
        status = {
            'skipped': False,
            'start': None,
            'inProgress': False,
            'complete': True,  # only while placeholder
            'end': None,
            'steps': 0,
            'stepsComplete': 0,
            'progress': None,
            '_note': 'preparation NOT YET IMPLEMENTED / placeholder only',
        }
        return status

    # currently only gives most recent job
    def _get_pipeline_status_detection(self):
        status = {
            'skipped': False,
            'start': None,
            'inProgress': False,
            'complete': False,
            'failed': False,
            'error': None,
            'end': None,
            'numModels': 0,
            'jobs': None,
            'numJobs': None,
            'numJobsActive': None,
            'numJobsFailed': None,
            'numAttempts': self.detection_attempts,
            'numAttemptsMax': MAX_DETECTION_ATTEMPTS,
            'numAssets': None,
            'numAnnotations': None,
            'steps': 0,
            'stepsComplete': 0,
            'progress': None,
        }
        # TODO i am not sure if this is the best count here, as there
        #   is config['updatedAssets'] which may actually need to be considered
        status['numAssets'] = len(self.get_assets())
        status['numAnnotations'] = len(self.get_all_annotations())

        #  self.stage == AssetGroupSightingStage.detection
        asset_group_config = self.asset_group.config
        if 'speciesDetectionModel' in asset_group_config:
            status['numModels'] = len(asset_group_config['speciesDetectionModel'])
        # whose idea was this?
        if (
            status['numModels'] == 1
            and asset_group_config['speciesDetectionModel'][0] == 'None'
        ):
            status['numModels'] = 0
        if status['numModels'] < 1:  # assumed detection skipped
            status['skipped'] = True
            status['complete'] = True
            status['steps'] = 1
            status['stepsComplete'] = 1
            return status

        status['inProgress'] = True

        if self.detection_attempts > MAX_DETECTION_ATTEMPTS:
            status['error'] = f'could not start after {MAX_DETECTION_ATTEMPTS} attempts'
            status['failed'] = True
            status['inProgress'] = False
            status['steps'] = 1

        # TODO needs more exploration - can we find out if we are waiting to start in celery?
        if not self.jobs:
            status['numJobs'] = 0
            status['numJobsActive'] = 0
            status['numJobsFailed'] = 0
            status['_debug'] = 'self.jobs is empty'
            return status

        # we reset failed here, as it looks like job started anyway?
        status['steps'] = 1
        status['stepsComplete'] = 1
        status['error'] = None
        status['failed'] = False
        status['numJobs'] = len(self.jobs)
        status['numJobsActive'] = 0
        status['numJobsFailed'] = 0

        job_info_list = []
        for job_id in self.jobs:
            job_info = {
                'id': job_id,
                'active': False,
                'error': None,
                'failed': False,
                # we only query sage for *active* jobs to save expense,
                #   so this being None is normal for inactive jobs
                'sage_status': None,
            }
            job = self.jobs[job_id]
            job_info['start'] = job.get('start')
            job_info['end'] = job.get('end')
            if job.get('active') is True:
                job_info['active'] = True
                status['numJobsActive'] += 1
                # we sh/could toggle active if this shows failure  TODO
                ss = None
                try:
                    ss = self.get_sage_job_status(job_id)
                except Exception as ex:
                    status[f'_debug_{job_id}'] = 'failed getting sage job status'
                    job_info['_get_sage_status_exception'] = str(ex)
                if ss:
                    job_info['sage_status'] = ss.get('jobstatus')
                    if ss.get('jobstatus') == 'exception':
                        job_info['error'] = 'sage exception'
                        job_info['failed'] = True
                        status['numJobsActive'] -= 1
                        status['numJobsFailed'] += 1
                        status[f'_debug_{job_id}'] = 'sage exception'
            job_info_list.append(job_info)

        # this should sort in chron order (the str() handles unset start case)
        status['jobs'] = sorted(job_info_list, key=lambda d: str(d['start']))

        # we now only factor in *most recent* job, in terms of
        #  failure, start/end, etc.  thus only 1 step
        status['steps'] += 1
        if status['jobs'][-1]['failed']:
            status['failed'] = True
            status['error'] = status['jobs'][-1]['error']
        else:
            status['stepsComplete'] += 1

        status['inProgress'] = status['jobs'][-1]['active']
        status['start'] = status['jobs'][-1]['start']
        status['end'] = status['jobs'][-1]['end']
        status['complete'] = not status['inProgress']
        if status['steps']:
            status['progress'] = status['stepsComplete'] / status['steps']
        return status

    # this is just for compatibility with sighting, but basically this is null
    def _get_pipeline_status_identification(self):
        status = {
            'skipped': False,
            'start': None,
            'inProgress': False,
            'complete': False,
            'failed': False,
            'error': None,
            'end': None,
            'jobs': None,
            'numJobs': None,
            'numJobsActive': None,
            'numJobsFailed': None,
            'matchingSetQueryPassed': None,
            'matchingSetQueryUsed': None,
            'matchingSetSize': None,
            'numAttempts': None,
            'numAttemptsMax': None,
            'idConfigs': None,
            'numAssets': len(self.get_assets()),
            'numAnnotations': len(self.get_all_annotations()),
            'steps': 0,
            'stepsComplete': 0,
            'progress': None,
            '_note': 'identification only included for consistency; meaningless on AssetGroupSighting',
        }
        return status

    @classmethod
    def get_sage_job_status(cls, job_id):
        return current_app.acm.request_passthrough_result('job.status', 'get', {}, job_id)

    # Build up list to print out status (calling function chooses what to collect and print)
    def get_jobs_debug(self, verbose):
        details = []
        for job_id in self.jobs.keys():
            details.append(self.jobs[job_id])
            details[-1]['type'] = 'AssetGroupSighting'
            details[-1]['object_guid'] = self.guid
            details[-1]['job_id'] = job_id

            if verbose:
                details[-1]['request'] = self.build_detection_request(
                    job_id, self.jobs[job_id]['model']
                )
                try:
                    sage_response = current_app.acm.request_passthrough_result(
                        'job.response', 'post', {}, job_id
                    )

                    details[-1]['response'] = sage_response
                except HoustonException as ex:
                    # Sage seems particularly flaky with this API
                    details[-1][
                        'response'
                    ] = f'Sage response caused HoustonException {ex.message}'

        return details

    def build_detection_request(self, job_uuid, model):
        from app.modules.ia_config_reader import IaConfig

        callback_url = url_for(
            'api.asset_groups_asset_group_sighting_detected',
            asset_group_sighting_guid=str(self.guid),
            job_guid=str(job_uuid),
            _external=True,
        )

        ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))
        detector_config = ia_config_reader.get_named_detector_config(model)

        assert 'start_detect' in detector_config

        model_config = {
            'endpoint': detector_config['start_detect'],
            'jobid': str(job_uuid),
            'callback_url': f'houston+{callback_url}',
            'callback_detailed': True,
        }
        model_config.update(detector_config)

        asset_urls = []
        if 'updatedAssets' in self.sighting_config:
            asset_urls = [
                url_for('api.assets_asset_src_raw_by_id', asset_guid=guid, _external=True)
                for guid in self.sighting_config['updatedAssets']
            ]
        else:
            for filename in self.sighting_config.get('assetReferences'):
                asset = self.asset_group.get_asset_for_file(filename)
                if not asset:
                    logging.warning(f'Asset ref {filename}, cannot find asset, skipping')
                    continue

                asset_url = url_for(
                    'api.assets_asset_src_raw_by_id',
                    asset_guid=str(asset.guid),
                    _external=True,
                )
                if asset_url not in asset_urls:
                    asset_urls.append(asset_url)

        # Sort the Asset URLs so that when processing the response we know which
        # content guid relates to which asset guid
        asset_urls.sort()
        model_config['image_uuid_list'] = json.dumps(
            [f'houston+{asset_url}' for asset_url in asset_urls]
        )
        return model_config

    def send_detection_to_sage(self, model):
        job_id = uuid.uuid4()
        detection_request = self.build_detection_request(job_id, model)
        log.info(f'Sending detection message to Sage for {model}')
        try:
            current_app.acm.request_passthrough_result(
                'job.detect_request',
                'post',
                {'params': detection_request},
                'cnn/lightnet',
            )
            from datetime import datetime  # NOQA

            self.jobs[str(job_id)] = {
                'model': model,
                'active': True,
                'start': datetime.utcnow().isoformat(),
                'asset_ids': [
                    uri.rsplit('/', 1)[-1]
                    for uri in json.loads(detection_request['image_uuid_list'])
                ],
            }
            # This is necessary because we can only mark self as modified if
            # we assign to one of the database attributes
            self.jobs = self.jobs

            with db.session.begin(subtransactions=True):
                db.session.merge(self)
        except HoustonException as ex:
            acm_status_code = ex.get_val('acm_status_code', None)

            # Celery has done it's job and called the function to generate the request and will not retry as it
            # only does that for RequestException, which includes various timeouts ec, not HoustonException

            if (
                ex.status_code == HTTPStatus.SERVICE_UNAVAILABLE
                or ex.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            ):
                if self.detection_attempts < MAX_DETECTION_ATTEMPTS:
                    log.warning(
                        f'Sage Detection on AssetGroupSighting({self.guid}) Job{job_id} failed to start, '
                        f'code: {ex.status_code}, acm_status_code: {acm_status_code}, retrying'
                    )
                    self.rerun_detection()

            log.warning(
                f'Sage Detection on AssetGroupSighting({self.guid}) Job{job_id} failed to start, '
                f'code: {ex.status_code}, acm_status_code: {acm_status_code}, giving up'
            )
            # Assuming some sort of persistent error in Sage
            self.job_complete(str(job_id))
            self.set_stage(AssetGroupSightingStage.curation)

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll ACM to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True

    def set_stage(self, stage, refresh=True):
        self.stage = stage
        with db.session.begin(subtransactions=True):
            db.session.merge(self)
        if refresh:
            db.session.refresh(self)

    def detected(self, job_id, response):
        log.info(f'Received Sage detection response on AssetGroupSighting {self.guid}')
        if self.stage != AssetGroupSightingStage.detection:
            raise HoustonException(
                log, f'AssetGroupSighting {self.guid} is not detecting'
            )

        job = self.jobs.get(str(job_id))
        if job is None:
            raise HoustonException(
                log, f'job_id {job_id} not found, self.jobs={self.jobs}'
            )

        status = response.get('status')
        if not status:
            raise HoustonException(log, 'No status in response from Sage')

        if status != 'completed':
            # Job Failed on Sage but move to curation so that user can create annotations manually and commit
            # Post MVP this may be a separate stage (that also permits annot creation and commit)
            self.set_stage(AssetGroupSightingStage.curation)
            self.job_complete(str(job_id))

            # This is not an exception as the message from Sage was valid
            msg = f'JobID {str(job_id)} failed with status: {status}, Sage result: {response.get("json_result")}'
            AuditLog.backend_fault(log, msg, self)
            return

        job_id_msg = response.get('jobid')
        if not job_id_msg:
            raise HoustonException(log, 'Must be a job id in the response')

        if job_id_msg != str(job_id):
            raise HoustonException(
                log,
                f'Job id in message {job_id_msg} must match job id in callback {job_id}',
            )

        json_result = response.get('json_result', None)

        if not json_result:
            raise HoustonException(log, 'No json_result in message from Sage')

        job['json_result'] = json_result
        with db.session.begin(subtransactions=True):
            self.jobs = self.jobs
            db.session.merge(self)

        sage_image_uuids = json_result.get('image_uuid_list', [])
        results_list = json_result.get('results_list', [])
        if len(sage_image_uuids) != len(results_list):
            raise HoustonException(
                log,
                f'image list len {len(sage_image_uuids)} does not match results len {len(results_list)}',
            )
        if len(sage_image_uuids) != len(job['asset_ids']):
            raise HoustonException(
                log,
                f'image list from sage {len(sage_image_uuids)} does not match local image list {len(job["asset_ids"])}',
            )

        annotations = []
        # Populate Asset Content guids, ordered by Asset Guids as that is the order they were sent in
        sorted_asset_ids = job['asset_ids']
        sorted_asset_ids.sort()
        log.debug(f'Received Image UUIDs {sage_image_uuids} in detection response')

        for i, asset_id in enumerate(sorted_asset_ids):
            asset = Asset.find(asset_id)
            if not asset:
                raise HoustonException(log, f'Asset Id {asset_id} not found')
            asset.content_guid = from_acm_uuid(sage_image_uuids[i])

            results = results_list[i]

            for annot_id in range(len(results)):
                annot_data = results[annot_id]
                content_guid = from_acm_uuid(annot_data.get('uuid', {}))
                ia_class = annot_data.get('class', None)
                # TODO sage returns "null" as the viewpoint, when it always
                # returns a viewpoint, we can remove the "or 'unknown'" part
                viewpoint = annot_data.get('viewpoint', None) or 'unknown'
                if not viewpoint or not ia_class:
                    raise HoustonException(
                        log,
                        f'Need a viewpoint "{viewpoint}" and a class "{ia_class}" in each of the results',
                    )

                bounds = Annotation.create_bounds(annot_data)

                annotations.append(
                    Annotation(
                        guid=uuid.uuid4(),
                        content_guid=content_guid,
                        asset=asset,
                        ia_class=ia_class,
                        viewpoint=viewpoint,
                        bounds=bounds,
                    )
                )

        for new_annot in annotations:
            AuditLog.system_create_object(log, new_annot, 'from Sage detection response')
            with db.session.begin(subtransactions=True):
                db.session.add(new_annot)

        db.session.refresh(self)

        self.job_complete(str(job_id))

    # Record that the asset has been updated for future re detection
    def asset_updated(self, asset):
        updated_assets = self.sighting_config.setdefault('updatedAssets', [])
        if asset.guid not in updated_assets:
            updated_assets.append(asset.guid)

        # Ensure it's written to DB
        self.config = self.config

    def rerun_detection(self, background=True):
        log.info('Rerunning Sage detection')
        if self.stage == AssetGroupSightingStage.curation:
            self.set_stage(AssetGroupSightingStage.detection)
            self.start_detection(background=background)
        elif self.stage == AssetGroupSightingStage.detection:
            if self.any_jobs_active():
                raise HoustonException(
                    log,
                    'Cannot rerun detection on AssetGroupSighting in detection stage with active jobs',
                )
            self.start_detection(background=background)
        else:
            raise HoustonException(
                log, f'Cannot rerun detection on AssetGroupSighting in {self.stage} stage'
            )

    def start_detection(self, background=True):
        from app.modules.asset_groups.tasks import sage_detection

        assert len(self.detection_configs) > 0
        assert self.stage == AssetGroupSightingStage.detection

        # Temporary restriction for MVP
        assert len(self.detection_configs) == 1
        for config in self.detection_configs:
            log.info(
                f'ia pipeline starting detection {config} on AssetGroupSighting {self.guid}'
            )
            self.detection_attempts += 1
            if background:
                # Call sage_detection in the background by doing .delay()
                sage_detection.delay(str(self.guid), config)
            else:
                sage_detection(str(self.guid), config)

    # Used to build the response to AssetGroupSighting GET
    def get_assets(self):
        assets = []
        if not self.sighting_config.get('assetReferences'):
            return assets
        for filename in self.sighting_config.get('assetReferences'):
            asset = self.asset_group.get_asset_for_file(filename)
            if asset:
                assets.append(asset)
            # If there is no asset this is a data integrity error which should be handled elsewhere, not here
        assets.sort(key=lambda ast: ast.guid)
        return assets

    # these may not be assigned etc, but simply exist
    def get_all_annotations(self):
        annots = []
        for asset in self.get_assets():
            if asset.annotations:
                annots += asset.annotations
        return annots

    def complete(self):
        for job_id in self.jobs:
            assert not self.jobs[job_id]['active']

        self.set_stage(AssetGroupSightingStage.processed)

    def job_complete(self, job_id_str):
        if job_id_str in self.jobs:
            with db.session.begin(subtransactions=True):
                self.jobs[job_id_str]['active'] = False
                self.jobs[job_id_str]['end'] = datetime.utcnow().isoformat()

                outstanding_jobs = []
                for job in self.jobs.keys():
                    if self.jobs[job]['active']:
                        outstanding_jobs.append(job)

                if len(outstanding_jobs) == 0:
                    # All complete, updatedAssets now in same sate as other assets so no need to store anymore
                    if 'updatedAssets' in self.sighting_config:
                        del self.sighting_config['updatedAssets']
                    self.config = self.config
                    self.set_stage(AssetGroupSightingStage.curation, refresh=False)
                    self.curation_start = datetime.utcnow()

                # This is necessary because we can only mark jobs as
                # modified if we assign to it
                self.jobs = self.jobs

                db.session.merge(self)
            db.session.refresh(self)
        else:
            log.warning(f'job_id {job_id_str} not found in AssetGroupSighting')

    def delete(self):
        AuditLog.delete_object(log, self)
        if self.sighting:
            self.sighting[0].delete_from_edm_and_houston()

        with db.session.begin(subtransactions=True):
            db.session.delete(self)

    def get_encounter_metadata(self, encounter_uuid):
        encounter_metadata = {}
        for encounter_num in range(len(self.sighting_config['encounters'])):
            if self.sighting_config['encounters'][encounter_num]['guid'] == str(
                encounter_uuid
            ):
                encounter_metadata = self.sighting_config['encounters'][encounter_num]
                break
        return encounter_metadata

    def add_annotation_to_encounter(self, encounter_guid, annot_guid):
        for encounter_num in range(len(self.sighting_config['encounters'])):
            encounter_metadata = self.sighting_config['encounters'][encounter_num]
            if encounter_metadata['guid'] == str(encounter_guid):
                if 'annotations' not in encounter_metadata.keys():
                    encounter_metadata['annotations'] = []
                if annot_guid not in encounter_metadata['annotations']:
                    encounter_metadata['annotations'].append(annot_guid)

    def remove_annotation_from_encounter(self, encounter_guid, annot_guid):
        for encounter_num in range(len(self.sighting_config['encounters'])):
            encounter_metadata = self.sighting_config['encounters'][encounter_num]
            if encounter_metadata['guid'] == str(encounter_guid):
                if (
                    'annotations' in encounter_metadata.keys()
                    and annot_guid in encounter_metadata['annotations']
                ):
                    self.sighting_config['encounters'][encounter_num][
                        'annotations'
                    ].remove(annot_guid)

    def remove_annotation(self, annot_guid):
        for encounter_num in range(len(self.sighting_config['encounters'])):
            encounter_metadata = self.sighting_config['encounters'][encounter_num]
            if (
                'annotations' in encounter_metadata.keys()
                and annot_guid in encounter_metadata['annotations']
            ):
                self.sighting_config['encounters'][encounter_num]['annotations'].remove(
                    annot_guid
                )

    def get_id_configs(self):
        return self.sighting_config.get('idConfigs', [])


class AssetGroup(GitStore):
    """
    AssetGroup database model.
    """

    GIT_STORE_NAME = 'asset_groups'

    GIT_STORE_DATABASE_PATH_CONFIG_NAME = 'ASSET_GROUP_DATABASE_PATH'

    guid = db.Column(db.GUID, db.ForeignKey('git_store.guid'), primary_key=True)

    asset_group_sightings = db.relationship(
        'AssetGroupSighting',
        back_populates='asset_group',
        order_by='AssetGroupSighting.guid',
        cascade='all, delete',
    )

    __mapper_args__ = {
        'polymorphic_identity': 'asset_group',
    }

    @classmethod
    def run_integrity(cls):
        result = {
            'assets_without_annots': [],
            'failed_sightings': [],
            'unknown_stage_sightings': [],
            'preparation_stage_sightings': [],
            'sightings_missing_assets': [],
            'jobless_detecting_sightings': [],
        }

        # Processed groups should have no assets without annots
        under_processed_groups = (
            db.session.query(AssetGroup)
            .join(AssetGroupSighting)
            .join(Asset)
            .filter(AssetGroupSighting.stage == AssetGroupSightingStage.processed)
            .filter(~Asset.annotations.any())
        ).all()

        if under_processed_groups:
            for group in under_processed_groups:
                hanging_assets = [
                    asset.guid for asset in group.assets if len(asset.annotations) == 0
                ]
                result['assets_without_annots'].append(
                    {
                        'group_guid': group.guid,
                        'asset_guids': hanging_assets,
                    }
                )
        result['failed_sightings'] = [
            sight.guid
            for sight in (
                db.session.query(AssetGroupSighting).filter(
                    AssetGroupSighting.stage == AssetGroupSightingStage.failed
                )
            ).all()
        ]

        result['unknown_stage_sightings'] = [
            sight.guid
            for sight in (
                db.session.query(AssetGroupSighting).filter(
                    AssetGroupSighting.stage == AssetGroupSightingStage.unknown
                )
            ).all()
        ]

        result['preparation_stage_sightings'] = [
            sight.guid
            for sight in (
                db.session.query(AssetGroupSighting).filter(
                    AssetGroupSighting.stage == AssetGroupSightingStage.preparation
                )
            ).all()
        ]

        # Having detecting sightings is perfectly valid but there may be reasons why they're
        # stuck in detecting. Only look at ones that are at least an hour old to avoid false positives
        import datetime

        an_hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        detecting_sightings = (
            db.session.query(AssetGroupSighting)
            .filter(AssetGroupSighting.stage == AssetGroupSightingStage.detection)
            .filter(AssetGroupSighting.created < an_hour_ago)
        ).all()

        # look for some possible reasons we're stuck in detection
        for sighting in detecting_sightings:
            missing_files = []
            for filename in sighting.config.get('assetReferences'):
                asset = sighting.asset_group.get_asset_for_file(filename)
                if not asset:
                    missing_files.append(filename)

            if missing_files:
                result['sightings_missing_assets'].append(
                    {'sighting_guid': sighting.guid, 'missing_files': missing_files}
                )
            if not sighting.jobs:
                result['jobless_detecting_sightings'].append(sighting.guid)

        return result

    def index_hook_obj(self, *args, **kwargs):
        for sighting in self.asset_group_sightings:
            sighting.index(*args, **kwargs)

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.asset_groups.schemas import CreateAssetGroupSchema

        return CreateAssetGroupSchema

    @classmethod
    def ensure_remote_delay(cls, asset_group):
        from app.extensions.git_store.tasks import ensure_remote

        ensure_remote.delay(str(asset_group.guid))

    def git_push_delay(self):
        from app.extensions.git_store.tasks import git_push

        git_push.delay(str(self.guid))

    def delete_remote_delay(self):
        from app.extensions.git_store.tasks import delete_remote

        delete_remote.delay(str(self.guid))

    def git_commit_metadata_hook(self, local_store_metadata):
        if 'frontend_sightings_data' not in local_store_metadata and self.config:
            metadata_request = self.config
            metadata_request['sightings'] = []
            for sighting in self.asset_group_sightings:
                metadata_request['sightings'].append(sighting.sighting_config)
            local_store_metadata['frontend_sightings_data'] = metadata_request

    @property
    def bulk_upload(self):
        return isinstance(self.config, dict) and self.config.get('uploadType') == 'bulk'

    def post_preparation_hook(self):
        if self.asset_group_sightings:
            for sighting in self.asset_group_sightings:
                sighting.post_preparation_hook()

    def is_partially_in_stage(self, stage):
        if self.asset_group_sightings:
            for sighting in self.asset_group_sightings:
                if sighting.stage == stage:
                    return True
        return False

    def is_completely_in_stage(self, stage):
        if self.asset_group_sightings:
            for sighting in self.asset_group_sightings:
                if sighting.stage != stage:
                    return False
        else:
            # If there are no sightings, the only stages that are valid are unknown and processed
            return stage in [
                AssetGroupSightingStage.unknown,
                AssetGroupSightingStage.processed,
            ]
        return True

    def is_detection_in_progress(self):
        return self.is_partially_in_stage(AssetGroupSightingStage.detection)

    def is_processed(self):
        return self.is_completely_in_stage(AssetGroupSightingStage.processed)

    def get_asset_group_sighting_for_annotation(self, annot):
        ret_ags = None
        for ags in self.asset_group_sightings:
            if ags.has_annotation(str(annot.guid)):
                ret_ags = ags
                break
        return ret_ags

    def get_asset_group_sightings_for_asset(self, asset):
        return [ags for ags in self.asset_group_sightings if ags.has_filename(asset.path)]

    def get_unprocessed_asset_group_sightings(self):
        return [
            ags
            for ags in self.asset_group_sightings
            if ags.stage != AssetGroupSightingStage.processed
        ]

    def remove_annotation_from_any_sighting(self, annot_guid):
        for sighting in self.asset_group_sightings:
            sighting.remove_annotation(str(annot_guid))

    def begin_ia_pipeline(self, metadata):
        # Temporary restriction for MVP
        assert len(metadata.detection_configs) == 1
        assert metadata.data_processed == AssetGroupMetadata.DataProcessed.complete
        import copy

        # Store the metadata in the AssetGroup but not the sightings (also keep detection), that is stored on the AssetGroupSightings
        self.config = dict(metadata.request)

        del self.config['sightings']

        input_files = []
        for sighting_meta in metadata.request['sightings']:
            input_files.extend(sighting_meta.get('assetReferences', []))
            # All encounters in the metadata need to be allocated a pseudo ID for later patching
            for encounter_num in range(len(sighting_meta['encounters'])):
                sighting_meta['encounters'][encounter_num]['guid'] = str(uuid.uuid4())

            AssetGroupSighting(
                asset_group=self,
                sighting_config=copy.deepcopy(sighting_meta),
                detection_configs=metadata.detection_configs,
            )

        # make sure the repo is created
        self.ensure_repository()

        description = 'Adding Creation metadata'
        if metadata.description != '':
            description = metadata.description

        self.git_commit(
            description,
            input_filenames=input_files,
            update=False,  # Delay the processing of the files, move to the background
            commit=False,  # Delay Git commit as well
        )

        return input_files

    def asset_updated(self, asset):
        for ags in self.get_asset_group_sightings_for_asset(asset):
            ags.asset_updated(asset)

    def delete(self):
        AuditLog.delete_object(log, self)
        with db.session.begin(subtransactions=True):
            for sighting in self.asset_group_sightings:
                sighting.delete()
        super(AssetGroup, self).delete()

    def delete_asset_group_sighting(self, asset_group_sighting):
        with db.session.begin(subtransactions=True):
            for asset in self.assets:
                asset_ags = self.get_asset_group_sightings_for_asset(asset)
                if asset_ags == [asset_group_sighting]:
                    asset.delete_cascade()
            asset_group_sighting.delete()
