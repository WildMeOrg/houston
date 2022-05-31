# -*- coding: utf-8 -*-
"""
AssetGroups database models
--------------------
"""
import copy
import datetime
import enum
import logging
import uuid

from flask import current_app, url_for
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog  # NOQA
from app.extensions import HoustonModel, db
from app.extensions.git_store import GitStore
from app.extensions.sage import from_sage_uuid
from app.modules.annotations.models import Annotation
from app.modules.assets.models import Asset
from app.modules.encounters.models import Encounter
from app.modules.individuals.models import Individual
from app.modules.names.models import DEFAULT_NAME_CONTEXT
from app.modules.sightings.models import Sighting, SightingStage
from app.modules.users.models import User
from app.utils import HoustonException
from flask_restx_patched._http import HTTPStatus

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
    detection_start = db.Column(db.DateTime, index=True, default=None, nullable=True)

    curation_start = db.Column(
        db.DateTime, index=True, default=datetime.datetime.utcnow, nullable=False
    )
    detection_attempts = db.Column(db.Integer, default=0, nullable=False)

    progress_detection_guid = db.Column(
        db.GUID, db.ForeignKey('progress.guid'), index=False, nullable=True
    )

    progress_detection = db.relationship(
        'Progress',
        foreign_keys='AssetGroupSighting.progress_detection_guid',
    )

    progress_identification_guid = db.Column(
        db.GUID, db.ForeignKey('progress.guid'), index=False, nullable=True
    )

    progress_identification = db.relationship(
        'Progress',
        foreign_keys='AssetGroupSighting.progress_identification_guid',
    )

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

    def setup(self):
        # Setup needs to happen after the AGS has been added to the database

        self.set_stage(AssetGroupSightingStage.preparation)

        if not self.asset_group.progress_preparation:
            self.post_preparation_hook()
        elif self.asset_group.progress_preparation.complete:
            self.post_preparation_hook()
        elif self.asset_group.progress_preparation.skipped:
            self.post_preparation_hook()
        elif self.asset_group.progress_preparation.percentage >= 99:
            # We sometimes create an AGS when the percentage is 99%
            self.post_preparation_hook()

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

        # Allow sightings to have no Assets, they go straight to curation
        if (
            'assetReferences' not in self.sighting_config
            or len(self.sighting_config['assetReferences']) == 0
        ):
            if self.progress_detection:
                self.progress_detection.skip('No assets were submitted')

            self.set_stage(AssetGroupSightingStage.curation)
            self.commit()

        elif len(self.detection_configs) == 1 and (
            not self.detection_configs[0] or self.detection_configs[0] == 'None'
        ):
            if self.progress_detection:
                self.progress_detection.skip('No detection config specified')

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
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.utils import Cleanup

        timer = ElapsedTime()

        if self.stage != AssetGroupSightingStage.curation:
            raise HoustonException(
                log,
                f'AssetGroupSighting {self.guid} is currently in {self.stage}, not curating cannot commit',
                obj=self,
            )

        if not self.sighting_config:
            raise HoustonException(
                log,
                f'AssetGroupSighting {self.guid} has no metadata',
                obj=self,
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
        if not self.sighting_config:
            return False
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

    # this is to mirror same method on Sighting
    def get_submission_time(self):
        return self.created

    def get_submission_time_isoformat(self):
        return self.get_submission_time().isoformat() + 'Z'

    # Don't store detection start time directly. It's either the creation time if we ever had detection
    # jobs or None if no detection was done (and hence no jobs exist)
    def get_detection_start_time(self):
        if self.detection_start:
            return self.detection_start.isoformat() + 'Z'
        return None

    # curation time is only valid if there are no active detection jobs and there were some assets
    # Either detection has completed or no detection jobs were run
    def get_curation_start_time(self):
        if (
            self.stage != AssetGroupSightingStage.detection
            and not self.any_jobs_active()
            and self.sighting_config
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
        # should we check for self.sighting_config here? or let it throw exception?
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
        from app.modules.annotations.schemas import BaseAnnotationSchema
        from app.modules.users.schemas import PublicUserSchema

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
            # Don't attempt to restart detection until we have had at least 10 minutes for celery to have a go
            if (
                not all_scheduled
                and datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
                > self.detection_start
            ):
                # TODO it would be nice to know if the scheduled tasks were for other AGS than this one
                # but at the moment, it's not clear how we could detect this
                log.warning(
                    f'{self.guid} is detecting but no detection jobs are running, '
                    'assuming Celery error and starting them again'
                )
            try:
                self.rerun_detection()
            except Exception:
                log.exception(f'{self} rerun_detection failed')
            return
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                current_app.sage.request_passthrough_result(
                    'engine.result', 'get', {}, job_id
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
            'curation': self._get_pipeline_status_curation(),
            'identification': self._get_pipeline_status_identification(),
            'now': datetime.datetime.utcnow().isoformat(),
            'stage': self.stage,
            'migrated': False,  # always false, but just for consistency with sighting
            'summary': {},
        }
        status['summary']['complete'] = (
            status['preparation']['complete']
            and status['detection']['complete']
            and status['curation']['complete']
            and status['identification']['complete']
        )
        # this is not the best math, but prob best we can do
        status['summary']['progress'] = (
            (status['preparation']['progress'] or 0)
            + (status['detection']['progress'] or 0)
            + (status['curation']['progress'] or 0)
            + (status['identification']['progress'] or 0)
        ) / 4
        return status

    def _get_pipeline_status_preparation(self):
        from app.modules.progress.models import ProgressStatus

        progress = self.progress_preparation
        # no progress object, do the best we can?
        if not progress:
            return {
                'skipped': None,
                'inProgress': False,
                'complete': True,
                'failed': False,
                'message': 'missing Progress',
                'steps': 0,
                'stepsComplete': 0,
                'progress': 1,
                'start': None,
                'end': None,
                'eta': None,
                'ahead': None,
                'status': None,
                'description': None,
            }

        status = {
            'skipped': progress.skipped,
            # should inProgress be dropped now?   TODO: discuss with FE team
            'inProgress': progress.status == ProgressStatus.created
            or progress.status == ProgressStatus.healthy,
            'complete': progress.complete,
            'failed': progress.status == ProgressStatus.failed,
            'message': progress.message,
            'steps': len(progress.steps) if progress.steps else 0,
            'stepsComplete': 0,  # TBD
            # using previously established 0.0-1.0 but maybe FE will want to swtich to 0-100
            'progress': progress.percentage / 100,
            'start': progress.created.isoformat() + 'Z',
            'end': None,
            # the following are new, thanks to Progress class
            'eta': progress.current_eta,
            'ahead': progress.ahead,
            'status': progress.status,
            'description': progress.description,
        }
        if progress.complete:
            status['end'] = progress.updated.isoformat() + 'Z'
        return status

    # currently only gives most recent job
    def _get_pipeline_status_detection(self):
        from app.utils import datetime_string_to_isoformat

        status = {
            'skipped': False,
            'start': None,
            'end': None,
            'inProgress': False,
            'complete': False,
            'failed': False,
            'message': None,
            'eta': None,
            'ahead': None,
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
            status['message'] = f'could not start after {MAX_DETECTION_ATTEMPTS} attempts'
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
        status['message'] = None
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
            job_info['start'] = datetime_string_to_isoformat(job.get('start'))
            job_info['end'] = datetime_string_to_isoformat(job.get('end'))
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
            status['message'] = status['jobs'][-1]['error']
        else:
            status['stepsComplete'] += 1

        status['inProgress'] = status['jobs'][-1]['active']
        status['start'] = status['jobs'][-1]['start']
        status['end'] = status['jobs'][-1]['end']
        status['complete'] = not status['inProgress']
        if status['steps']:
            status['progress'] = status['stepsComplete'] / status['steps']
        return status

    def _get_pipeline_status_curation(self):

        status = {
            'skipped': False,
            'start': self.get_curation_start_time(),
            'end': None,
            'inProgress': self.stage == AssetGroupSightingStage.curation,
            'complete': False,
            'failed': False,
            'progress': 0.0,
        }
        # If there are no assets in an asset group sighting, curation will be skipped.
        if len(self.get_assets()) < 1:
            status['skipped'] = True
            status['progress'] = 1.0

        elif status['inProgress']:
            # this is the "Fisher progress constant" and on average it has zero error
            status['progress'] = 0.5
            # detection may have been skipped and we need to infer this
            if not status['start']:
                annotations = self.get_all_annotations()
                if annotations and len(annotations) > 1:
                    first_annot_created = min(ann.created for ann in annotations)
                    status['start'] = first_annot_created.isoformat() + 'Z'

        return status

    # this is just for compatibility with sighting, but basically this is null
    def _get_pipeline_status_identification(self):
        status = {
            'skipped': False,
            'start': None,
            'end': None,
            'inProgress': False,
            'complete': False,
            'failed': False,
            'message': None,
            'eta': None,
            'ahead': None,
            'jobs': None,
            'numJobs': None,
            'numJobsActive': None,
            'numJobsFailed': None,
            'matchingSetQueryPassed': None,
            'matchingSetQueryUsed': None,
            # 'matchingSetSize': None,
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
        return current_app.sage.request_passthrough_result(
            'job.status', 'get', {}, job_id
        )

    # Build up list to print out status (calling function chooses what to collect and print)
    def get_jobs_debug(self, verbose):
        details = []
        for job_id in self.jobs.keys():
            details.append(self.jobs[job_id])
            details[-1]['type'] = 'AssetGroupSighting'
            details[-1]['object_guid'] = self.guid
            details[-1]['job_id'] = job_id

            if verbose:
                detection_request, _ = self.build_detection_request(
                    job_id, self.jobs[job_id]['model']
                )
                details[-1]['request'] = detection_request
                try:
                    sage_response = current_app.sage.request_passthrough_result(
                        'engine.result', 'get', {}, job_id
                    )

                    details[-1]['response'] = sage_response
                except HoustonException as ex:
                    # Sage seems particularly flaky with this API
                    details[-1][
                        'response'
                    ] = f'Sage response caused HoustonException {ex.message}'

        return details

    def build_detection_request(self, job_uuid, model, preload=True):
        from app.extensions.sage import to_sage_uuid
        from app.modules.ia_config_reader import IaConfig

        callback_url = url_for(
            'api.asset_groups_asset_group_sighting_detected',
            asset_group_sighting_guid=str(self.guid),
            job_guid=str(job_uuid),
            _external=True,
        )

        model_config = {
            'jobid': str(job_uuid),
            'callback_url': f'houston+{callback_url}',
            'callback_detailed': True,
        }

        ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))
        detector_config = ia_config_reader.get_named_detector_config(model)
        model_config.update(detector_config)

        assets = []
        if 'updatedAssets' in self.sighting_config:
            for guid in self.sighting_config['updatedAssets']:
                asset = Asset.query.get(guid)
                if not asset:
                    logging.warning(f'Asset ref {guid}, cannot find asset, skipping')
                    continue
                assets.append(asset)
        else:
            for filename in self.sighting_config.get('assetReferences'):
                asset = self.asset_group.get_asset_for_file(filename)
                if not asset:
                    logging.warning(f'Asset ref {filename}, cannot find asset, skipping')
                    continue
                assets.append(asset)

        asset_sage_data = []

        if preload:
            # Ensure that the assets exist on Sage
            for asset in assets:
                asset.sync_with_sage(ensure=True)
                asset_sage_data.append(
                    (
                        to_sage_uuid(asset.content_guid),
                        asset.guid,
                    )
                )

            asset_sage_data.sort(key=lambda data: data[0]['__UUID__'])
        else:
            for asset in assets:
                asset_sage_data.append(
                    (
                        url_for(
                            'api.assets_asset_src_raw_by_id',
                            asset_guid=str(asset.guid),
                            _external=True,
                        ),
                        asset.guid,
                    )
                )

            # Sort the Asset URLs so that when processing the response we know which
            # content guid relates to which asset guid
            asset_sage_data.sort(key=lambda data: data[0])

        asset_sage_values = []
        asset_guids = []
        for asset_sage_value, asset_guid in asset_sage_data:
            if asset_sage_value in asset_sage_values:
                # Deduplicate
                continue
            asset_sage_values.append(asset_sage_value)
            asset_guids.append(asset_guid)

        model_config['image_uuid_list'] = asset_sage_values

        return model_config, asset_guids

    def send_detection_to_sage(self, model):
        try:
            if self.progress_detection:
                self.progress_detection.set(2)

            job_id = uuid.uuid4()
            job_id_str = str(job_id)
            detection_request, asset_guids = self.build_detection_request(job_id, model)
            log.info(f'Sending detection message to Sage for {model}')
            log.info('detection_request = {!r}'.format(detection_request))
            log.info('asset_guids = {!r}'.format(asset_guids))

            if self.progress_detection:
                self.progress_detection.set(3)

            try:
                sage_job_uuid = current_app.sage.request_passthrough_result(
                    'engine.detect',
                    'post',
                    {'json': detection_request},
                )
                sage_guid = uuid.UUID(sage_job_uuid)
                assert sage_guid == job_id

                if self.progress_detection:
                    self.progress_detection.set(4)

                # Immediately bump the number of attempts
                with db.session.begin(subtransactions=True):
                    self.detection_attempts += 1

                if self.progress_detection:
                    self.progress_detection.set(5)

                with db.session.begin(subtransactions=True):
                    if self.jobs is None:
                        self.jobs = {}

                    self.jobs[job_id_str] = {
                        'model': model,
                        'active': True,
                        'start': datetime.datetime.utcnow().isoformat(),
                        'asset_guids': asset_guids,
                    }

                    self.jobs = self.jobs
                    log.info(
                        f'Started Detection job, on AssetGroupSighting {self.guid}, self.jobs= {self.jobs}'
                    )
                    self.detection_attempts += 1
                    db.session.merge(self)

                db.session.refresh(self)

                assert self.jobs and job_id_str in self.jobs

                if self.progress_detection:
                    self.progress_detection.set(6)

                if self.progress_detection:
                    with db.session.begin():
                        self.progress_detection.sage_guid = sage_guid
                        db.session.merge(self.progress_detection)

                if self.progress_detection:
                    self.progress_detection.set(10)
            except HoustonException as ex:
                sage_status_code = ex.get_val('sage_status_code', None)

                # If the progress_detection has a progress percentage of 4%, we have failed prior to
                # incrementing self.detection_attempts.  If the progress is less than 4, then we never actually send
                # the job to Sage for detection
                if self.progress_detection and self.progress_detection.percentage == 4:
                    with db.session.begin(subtransactions=True):
                        self.detection_attempts += 1
                    db.session.refresh(self)

                # Celery has done it's job and called the function to generate the request and will not retry as it
                # only does that for RequestException, which includes various timeouts ec, not HoustonException
                if (
                    ex.status_code == HTTPStatus.SERVICE_UNAVAILABLE
                    or ex.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
                ) and self.detection_attempts < MAX_DETECTION_ATTEMPTS:
                    log.warning(
                        f'Sage Detection on AssetGroupSighting({self.guid}) Job{job_id} failed to start, '
                        f'code: {ex.status_code}, sage_status_code: {sage_status_code}, retrying'
                    )
                    self.rerun_detection()
                else:
                    log.warning(
                        f'Sage Detection on AssetGroupSighting({self.guid}) Job{job_id} failed to start, '
                        f'code: {ex.status_code}, sage_status_code: {sage_status_code}, giving up'
                    )
                    # Assuming some sort of persistent error in Sage
                    self.job_complete(job_id)
                    self.set_stage(AssetGroupSightingStage.curation)
        except Exception as ex:
            if self.progress_detection:
                self.progress_detection.fail(str(ex))
            raise

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll Sage to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True

    def set_stage(self, stage, refresh=True):
        with db.session.begin(subtransactions=True):
            self.stage = stage
            db.session.merge(self)
        if refresh:
            db.session.refresh(self)

    def detected(self, job_id, response):
        try:
            log.info(
                f'Received Sage detection response on AssetGroupSighting {self.guid}'
            )
            if self.stage != AssetGroupSightingStage.detection:
                raise HoustonException(
                    log, f'AssetGroupSighting {self.guid} is not detecting', obj=self
                )

            job = self.jobs.get(str(job_id))
            if job is None:
                raise HoustonException(
                    log,
                    f'AssetGroupSighting {self.guid} job_id {job_id} not found, self.jobs={self.jobs}',
                    obj=self,
                )

            status = response.get('status')
            if not status:
                raise HoustonException(log, 'No status in response from Sage', obj=self)

            if status != 'completed':
                # Job Failed on Sage but move to curation so that user can create annotations manually and commit
                # Post MVP this may be a separate stage (that also permits annot creation and commit)
                self.set_stage(AssetGroupSightingStage.curation)
                self.job_complete(job_id)

                # This is not an exception as the message from Sage was valid
                msg = f'JobID {str(job_id)} failed with status: {status}, Sage result: {response.get("json_result")}'
                AuditLog.backend_fault(log, msg, self)
                return

            job_id_msg = response.get('jobid')
            if not job_id_msg:
                raise HoustonException(log, 'Must be a job id in the response', obj=self)

            if job_id_msg != str(job_id):
                raise HoustonException(
                    log,
                    f'Job id in message {job_id_msg} must match job id in callback {job_id}',
                    obj=self,
                )

            json_result = response.get('json_result', None)

            if not json_result:
                raise HoustonException(
                    log, 'No json_result in message from Sage', obj=self
                )

            job['result'] = json_result
            with db.session.begin(subtransactions=True):
                self.jobs = self.jobs
                # A detection job succeeded, let's zero out the number of attempts
                self.detection_attempts = 0
                db.session.merge(self)

            asset_guids = job['asset_guids']
            sage_image_uuids = json_result.get('image_uuid_list', [])
            results_list = json_result.get('results_list', [])

            if len(sage_image_uuids) != len(results_list):
                raise HoustonException(
                    log,
                    f'image list len {len(sage_image_uuids)} does not match results len {len(results_list)}',
                    obj=self,
                )
            if len(sage_image_uuids) != len(asset_guids):
                raise HoustonException(
                    log,
                    f'image list from sage {len(sage_image_uuids)} does not match local image list {len(job["asset_ids"])}',
                    obj=self,
                )

            with db.session.begin(subtransactions=True):
                assets = []
                annotations = []

                zipped = zip(asset_guids, sage_image_uuids, results_list)
                for asset_guid, sage_image_uuid, results in zipped:
                    asset = Asset.find(asset_guid)
                    if not asset:
                        raise HoustonException(log, f'Asset {asset_guid} not found')

                    assets.append(asset)

                    sage_content_guid = from_sage_uuid(sage_image_uuid)

                    if asset.content_guid is not None:
                        try:
                            assert (
                                asset.content_guid == sage_content_guid
                            ), 'The content GUID for {!r} is a mismatch'.format(asset)
                        except Exception:
                            # Get the content GUID fresh from Sage and double check
                            asset.sync_with_sage(ensure=True, force=True)
                            if asset.content_guid != sage_content_guid:
                                raise
                    else:
                        asset.content_guid = sage_content_guid

                    for result in results:

                        content_guid = from_sage_uuid(result.get('uuid', None))
                        ia_class = result.get('class', None)
                        # TODO sage returns "null" as the viewpoint, when it always
                        # returns a viewpoint, we can remove the "or 'unknown'" part
                        viewpoint = result.get('viewpoint', None) or 'unknown'
                        if not viewpoint or not ia_class:
                            raise HoustonException(
                                log,
                                f'Need a viewpoint "{viewpoint}" and a class "{ia_class}" in each of the results',
                                obj=self,
                            )

                        bounds = Annotation.create_bounds(result)

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

                for annotation in annotations:
                    AuditLog.system_create_object(
                        log, annotation, 'from Sage detection response'
                    )
                    db.session.add(annotation)

                for asset in assets:
                    db.session.merge(asset)

            db.session.refresh(self)

            self.job_complete(job_id)
            AuditLog.audit_log_object(
                log, self, f'Detection for AssetGroupSighting {self.guid} succeeded'
            )

            if self.progress_detection:
                self.progress_detection.set(100)
        except Exception as ex:
            if self.progress_detection:
                self.progress_detection.fail(str(ex))
            raise

    # Record that the asset has been updated for future re detection
    def asset_updated(self, asset):
        updated_assets = self.sighting_config.setdefault('updatedAssets', [])
        if asset.guid not in updated_assets:
            updated_assets.append(asset.guid)

        # Ensure it's written to DB
        self.config = self.config

    def rerun_detection(self, foreground=None):
        if self.detection_attempts >= MAX_DETECTION_ATTEMPTS:
            message = f'Detection on AssetGroupSighting({self.guid}) failed. Already had '
            message += f'{self.detection_attempts} attempts, assuming a persistent error and moving to curation'
            AuditLog.audit_log_object(log, self, message)

            # Assuming some sort of persistent error in Sage
            self.set_stage(AssetGroupSightingStage.curation)
            return

        log.info('Rerunning Sage detection')

        if foreground is None:
            foreground = current_app.testing

        if self.stage == AssetGroupSightingStage.curation:
            self.set_stage(AssetGroupSightingStage.detection)
            self.start_detection(foreground=foreground)
        elif self.stage == AssetGroupSightingStage.detection:
            if self.any_jobs_active():
                raise HoustonException(
                    log,
                    'Cannot rerun detection on AssetGroupSighting in detection stage with active jobs',
                    obj=self,
                )
            self.start_detection(foreground=foreground)
        else:
            raise HoustonException(
                log,
                f'Cannot rerun detection on AssetGroupSighting in {self.stage} stage',
                obj=self,
            )

    def init_progress_detection(self, overwrite=False):
        from app.modules.progress.models import Progress

        if self.progress_detection:
            if not overwrite:
                log.warning(
                    'Asset Group Sighting %r already has a progress detection %r'
                    % (
                        self,
                        self.progress_detection,
                    )
                )
                return

        progress = Progress(
            description='Sage Detection for AssetGroupSighting {!r}'.format(self.guid)
        )
        with db.session.begin():
            db.session.add(progress)

        with db.session.begin():
            self.progress_detection_guid = progress.guid
            db.session.merge(self)

        # Assign the parent's progress
        self.asset_group.init_progress_detection()  # Ensure initialized

        if self.progress_detection and self.asset_group.progress_detection:
            with db.session.begin():
                self.progress_detection.parent_guid = (
                    self.asset_group.progress_detection.guid
                )
            db.session.merge(self.progress_detection)

        db.session.refresh(self)

    def init_progress_identification(self, overwrite=False):
        from app.modules.progress.models import Progress

        if self.progress_identification:
            if not overwrite:
                log.warning(
                    'Asset Group Sighting %r already has a progress identification %r'
                    % (
                        self,
                        self.progress_identification,
                    )
                )
                return

        progress = Progress(
            description='Sage identification for AssetGroupSighting {!r}'.format(
                self.guid
            )
        )
        with db.session.begin():
            db.session.add(progress)

        with db.session.begin():
            self.progress_identification_guid = progress.guid
            db.session.merge(self)

        # Assign the parent's progress
        self.asset_group.init_progress_identification()  # Ensure initialized

        if self.progress_identification and self.asset_group.progress_identification:
            with db.session.begin():
                self.progress_identification.parent_guid = (
                    self.asset_group.progress_identification.guid
                )
            db.session.merge(self.progress_identification)

        db.session.refresh(self)

    def start_detection(self, foreground=None):
        if foreground is None:
            foreground = current_app.testing

        self.init_progress_detection(overwrite=True)

        if self.progress_detection:
            # Set the status to healthy and 0%
            self.progress_detection = self.progress_detection.config()

        assert len(self.detection_configs) > 0
        assert self.stage == AssetGroupSightingStage.detection

        # Temporary restriction for MVP
        assert len(self.detection_configs) == 1
        for config in self.detection_configs:
            AuditLog.audit_log_object(
                log,
                self,
                f'Starting detection {config} on AssetGroupSighting {self.guid}',
            )

            if foreground:
                self.send_detection_to_sage(config)
                promise = None
            else:
                from app.modules.asset_groups.tasks import sage_detection

                promise = sage_detection.delay(str(self.guid), config)

            if self.progress_detection and promise:
                if self.progress_detection:
                    self.progress_detection.set(1)
                with db.session.begin():
                    self.progress_detection.celery_guid = promise.id
                    db.session.merge(self.progress_detection)
        self.detection_start = datetime.datetime.utcnow()

    # Used to build the response to AssetGroupSighting GET
    def get_assets(self):
        assets = []
        if not self.sighting_config or not self.sighting_config.get('assetReferences'):
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

    def job_complete(self, job_id):
        if not isinstance(job_id, str):
            job_id = str(job_id)

        if job_id in self.jobs:
            with db.session.begin(subtransactions=True):
                self.jobs[job_id]['active'] = False
                self.jobs[job_id]['end'] = datetime.datetime.utcnow().isoformat()

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
                    self.curation_start = datetime.datetime.utcnow()

                # This is necessary because we can only mark jobs as
                # modified if we assign to it
                self.jobs = self.jobs

                db.session.merge(self)
            db.session.refresh(self)
        else:
            log.warning(f'job_id {job_id} not found in AssetGroupSighting')

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

        ags_list = []
        with db.session.begin(subtransactions=True):
            input_files = []
            for sighting_meta in metadata.request['sightings']:
                input_files.extend(sighting_meta.get('assetReferences', []))
                # All encounters in the metadata need to be allocated a pseudo ID for later patching
                for encounter_num in range(len(sighting_meta['encounters'])):
                    sighting_meta['encounters'][encounter_num]['guid'] = str(uuid.uuid4())

                # Start by writing to DB so that all rollback on failure works
                ags = AssetGroupSighting(
                    asset_group=self,
                    sighting_config=copy.deepcopy(sighting_meta),
                    detection_configs=metadata.detection_configs,
                )
                db.session.add(ags)
                ags_list.append(ags)

        db.session.refresh(self)

        for ags in ags_list:
            # Refresh each AGS to load its GUID and perform any lingering setup now that it is in the database
            db.session.refresh(ags)
            ags.setup()
            AuditLog.user_create_object(log, ags)

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
