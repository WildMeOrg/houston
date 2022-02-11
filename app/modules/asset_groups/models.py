# -*- coding: utf-8 -*-
"""
AssetGroups database models
--------------------
"""
import copy
import enum
from flask import current_app
from flask_login import current_user  # NOQA
from datetime import datetime  # NOQA
from app.extensions import db, HoustonModel
import app.extensions.logging as AuditLog  # NOQA
from app.extensions.git_store import GitStore
from app.modules.annotations.models import Annotation
from app.modules.assets.models import Asset
from app.modules.encounters.models import Encounter
from app.modules.sightings.models import Sighting, SightingStage
from app.modules.users.models import User
from app.utils import HoustonException

import logging
import uuid
import json
from urllib.parse import urljoin

from .metadata import AssetGroupMetadata

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AssetGroupSightingStage(str, enum.Enum):
    unknown = 'unknown'
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

    def __init__(self, asset_group, sighting_config, detection_configs):
        self.asset_group = asset_group
        self.config = sighting_config

        # Start by writing to DB so that all rollback on failure works
        with db.session.begin(subtransactions=True):
            db.session.add(self)
        db.session.refresh(self)

        # Allow sightings to have no Assets, they go straight to curation
        if (
            'assetReferences' not in self.config
            or len(self.config['assetReferences']) == 0
        ):
            self.stage = AssetGroupSightingStage.curation
            self.commit()

        elif len(detection_configs) == 1 and (
            not detection_configs[0] or detection_configs[0] == 'None'
        ):
            self.stage = AssetGroupSightingStage.curation
        else:
            self.stage = AssetGroupSightingStage.detection

        if self.stage == AssetGroupSightingStage.detection:
            try:
                self.start_detection()

            except HoustonException as ex:
                self.delete()
                raise ex
        AuditLog.user_create_object(log, self)

    def commit(self):
        from app.modules.utils import Cleanup
        from app.extensions.elapsed_time import ElapsedTime

        timer = ElapsedTime()

        if self.stage != AssetGroupSightingStage.curation:
            raise HoustonException(
                log,
                f'AssetGroupSighting {self.guid} is currently {self.stage}, not curating cannot commit',
            )

        if not self.config:
            raise HoustonException(
                log,
                f'AssetGroupSighting {self.guid} has no metadata',
            )
        cleanup = Cleanup('AssetGroup')

        # Create sighting in EDM
        try:
            # Don't send the encounter guids. EDM doesn't use them but they confuse anyone reading logs
            sent_data = self.config
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

        # encounters via self.config and edm (result_data) need to have same count!
        if ('encounters' in self.config and 'encounters' not in result_data) or (
            'encounters' not in self.config and 'encounters' in result_data
        ):
            cleanup.rollback_and_houston_exception(
                log,
                'Missing encounters between requested config and result',
                'Sighting.post missing encounters in one of %r or %r'
                % (self.config, result_data),
            )
        if not len(self.config['encounters']) == len(result_data['encounters']):
            cleanup.rollback_and_houston_exception(
                log,
                'Imbalance in encounters between data and result',
                'Sighting.post imbalanced encounters in %r or %r'
                % (self.config, result_data),
            )

        sighting = Sighting(
            guid=result_data['id'],
            # asset_group_sighting=self,  -- see note below
            name=self.config.get('name', ''),
            stage=SightingStage.identification,
            version=result_data.get('version', 2),
        )
        try:
            sighting.set_time_from_data(self.config)
        except ValueError as ve:
            cleanup.rollback_and_abort(
                f'Problem with sighting time/timeSpecificity values: {str(ve)}',
                f"invalid time ({self.config.get('time')}) or timeSpecificity ({self.config.get('timeSpecificity')}): {str(ve)}",
                error_fields=['time'],
            )
        if not sighting.time:
            cleanup.rollback_and_houston_exception(
                log,
                'Must have time/timeSpecificity values',
                'Must have time/timeSpecificity values',
            )
        # we do not set this in the Sighting() constructor above, as a failure due to `time` value above
        #   causes an attempt to persist `sighting`, which we do not want
        sighting.set_asset_group_sighting(self)
        with db.session.begin(subtransactions=True):
            db.session.add(sighting)
        # Add the assets for all of the encounters to the created sighting object
        for reference in self.config.get('assetReferences', []):
            asset = self.asset_group.get_asset_for_file(reference)
            assert asset
            sighting.add_asset(asset)

        cleanup.add_object(sighting)

        for encounter_num in range(len(self.config['encounters'])):
            req_data = self.config['encounters'][encounter_num]
            res_data = result_data['encounters'][encounter_num]
            try:
                owner_guid = self.asset_group.owner_guid
                if 'ownerEmail' in req_data:
                    owner_email = req_data['ownerEmail']
                    encounter_owner = User.find(email=owner_email)
                    # Validated in the metadata code so must be correct
                    assert encounter_owner
                    owner_guid = encounter_owner.guid

                assert 'guid' in req_data
                new_encounter = Encounter(
                    guid=res_data['id'],
                    version=res_data.get('version', 2),
                    owner_guid=owner_guid,
                    asset_group_sighting_encounter_guid=req_data['guid'],
                    submitter_guid=self.asset_group.submitter_guid,
                    public=self.asset_group.anonymous,
                )
                new_encounter.set_time_from_data(req_data)

                AuditLog.user_create_object(
                    log, new_encounter, f'for owner {owner_guid}'
                )

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

        # AssetGroupSighting is finished, all subsequent processing is on the Sighting
        self.complete()
        sighting.ia_pipeline()

        num_encounters = len(self.config['encounters'])
        AuditLog.user_create_object(
            log, sighting, f'with {num_encounters} encounter(s)', duration=timer.elapsed()
        )

        return sighting

    def has_filename(self, filename):
        return (
            filename in self.config.get('assetReferences', []) if self.config else False
        )

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
        if self.jobs:
            return self.created.isoformat() + 'Z'
        return None

    # curation time is only valid if there are no active detection jobs and there were some assets
    # Either detection has completed or no detection jobs were run
    def get_curation_start_time(self):
        if (
            not self.any_jobs_active()
            and 'assetReferences' in self.config.keys()
            and len(self.config['assetReferences']) != 0
        ):
            return self.curation_start.isoformat() + 'Z'
        return None

    # Returns a percentage complete value 0-100
    def get_completion(self):
        # Design allows for these limits to be configured later, potentially this data could be project specific
        stage_base_sizes = {
            AssetGroupSightingStage.unknown: 0,
            AssetGroupSightingStage.detection: 0,
            AssetGroupSightingStage.curation: 10,
            AssetGroupSightingStage.processed: 30,  # 40 for identification 20 for review
            AssetGroupSightingStage.failed: 100,  # complete, even if failed
        }
        completion = stage_base_sizes[self.stage]

        # some stages are either all or nothing, these just use the base sizes above.
        # For those that have granularity we need to know the size range available and estimate how much has been done
        if self.stage == AssetGroupSightingStage.detection:
            if self.jobs:
                size_range = (
                    stage_base_sizes[AssetGroupSightingStage.curation]
                    - stage_base_sizes[self.stage]
                )
                complete_jobs = [job for job in self.jobs.values() if not job['active']]
                completion += size_range * (len(complete_jobs) / len(self.jobs))
        elif self.stage == AssetGroupSightingStage.processed:
            assert len(self.sighting) == 1
            size_range = 100 - stage_base_sizes[self.stage]
            sighting_completion = self.sighting[0].get_completion()
            completion += (sighting_completion / 100) * size_range

        # calculation generates a floating point value, reporting that would be claiming precision without accuracy
        return round(completion)

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
        value = self.config.get(field) if isinstance(self.config, dict) else None
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
        encounters = self.config and self.config.get('encounters') or []
        enc_json = None
        for encounter in encounters:
            if encounter['guid'] == str(encounter_guid):
                enc_json = self._augment_encounter_json(encounter)
                break
        return enc_json

    def get_encounters_json(self):
        encounters = self.config and self.config.get('encounters') or []
        enc_json = []
        for encounter in encounters:
            enc_json.append(self._augment_encounter_json(encounter))

        return enc_json

    @classmethod
    def check_jobs(cls):
        for asset_group_sighting in AssetGroupSighting.query.all():
            asset_group_sighting.check_all_job_status()

    def check_all_job_status(self):
        jobs = self.jobs
        if not jobs:
            return
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                current_app.acm.request_passthrough_result(
                    'job.response', 'post', {}, job_id
                )
                # TODO Process response
                # TODO If UTC Start more than {arbitrary limit} ago.... do something

    @classmethod
    def print_jobs(cls):
        for asset_group_sighting in AssetGroupSighting.query.all():
            asset_group_sighting.print_active_jobs()

    def print_active_jobs(self):
        jobs = self.jobs
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                log.warning(
                    f"AssetGroupSighting:{self.guid} Job:{job_id} Model:{job['model']} UTC Start:{job['start']}"
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
    def get_job_details(self, verbose):
        from copy import deepcopy

        details = deepcopy(self.jobs)
        if verbose:
            for job_id in self.jobs.keys():
                details[job_id]['request'] = self.build_detection_request(
                    job_id, self.jobs[job_id]['model']
                )
                details[job_id]['response'] = current_app.acm.request_passthrough_result(
                    'job.response', 'post', {}, job_id
                )

        return details

    def build_detection_request(self, job_uuid, model):
        from app.modules.ia_config_reader import IaConfig

        base_url = current_app.config.get('BASE_URL')
        callback_url = urljoin(
            base_url,
            f'/api/v1/asset_groups/sighting/{str(self.guid)}/sage_detected/{str(job_uuid)}',
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
        asset_url = urljoin(base_url, '/api/v1/assets/src_raw/')

        asset_guids = []
        if 'updatedAssets' in self.config:
            asset_guids = self.config['updatedAssets']
        else:
            for filename in self.config.get('assetReferences'):
                asset = self.asset_group.get_asset_for_file(filename)
                assert asset
                if asset.guid not in asset_guids:
                    asset_guids.append(asset.guid)

        model_config['image_uuid_list'] = json.dumps(
            [
                f'houston+{urljoin(asset_url, str(asset_guid))}'
                for asset_guid in asset_guids
            ]
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
                'start': datetime.utcnow(),
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
        except HoustonException:
            log.warning(
                f'Sage Detection on AssetGroupSighting({self.guid}) Job{job_id} failed to start'
            )
            # TODO Celery will retry, do we want it to?
            self.stage = AssetGroupSightingStage.failed

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll ACM to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True

    def set_stage(self, stage):
        self.stage = stage
        with db.session.begin(subtransactions=True):
            db.session.merge(self)

    def detected(self, job_id, response):
        log.info(f'Received Sage detection response on AssetGroupSighting {self.guid}')
        if self.stage != AssetGroupSightingStage.detection:
            raise HoustonException(
                log, f'AssetGroupSighting {self.guid} is not detecting'
            )

        job = self.jobs.get(str(job_id))
        if job is None:
            raise HoustonException(log, f'job_id {job_id} not found')

        status = response.get('status')
        if not status:
            raise HoustonException(log, 'No status in response from Sage')

        if status != 'completed':
            self.set_stage(AssetGroupSightingStage.failed)
            # This is not an exception as the message from Sage was valid
            msg = f'JobID {str(job_id)} failed with status: {status} exception: {response.get("json_result")}'
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
        self.jobs = self.jobs
        with db.session.begin(subtransactions=True):
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
        for i, asset_id in enumerate(job['asset_ids']):
            asset = Asset.find(asset_id)
            if not asset:
                raise HoustonException(log, f'Asset Id {asset_id} not found')

            results = results_list[i]

            for annot_id in range(len(results)):
                annot_data = results[annot_id]
                content_guid = annot_data.get('uuid', {}).get('__UUID__')
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
        self.job_complete(str(job_id))

    # Record that the asset has been updated for future re detection
    def asset_updated(self, asset):
        updated_assets = self.config.setdefault('updatedAssets', [])
        if asset.guid not in updated_assets:
            updated_assets.append(asset.guid)

        # Ensure it's written to DB
        self.config = self.config

    def rerun_detection(self):
        log.info('Rerunning Sage detection')
        if self.stage == AssetGroupSightingStage.curation:
            self.stage = AssetGroupSightingStage.detection
            self.start_detection()
        else:
            raise HoustonException(
                log, f'Cannot rerun detection on AssetGroupSighting in {self.stage} stage'
            )

    def start_detection(self):
        from app.modules.asset_groups.tasks import sage_detection

        asset_group_config = self.asset_group.config
        assert 'speciesDetectionModel' in asset_group_config
        assert self.stage == AssetGroupSightingStage.detection

        # Temporary restriction for MVP
        assert len(asset_group_config['speciesDetectionModel']) == 1
        for config in asset_group_config['speciesDetectionModel']:
            log.info(
                f'ia pipeline starting detection {config} on AssetGroupSighting {self.guid}'
            )
            # Call sage_detection in the background by doing .delay()
            sage_detection.delay(str(self.guid), config)

    # Used to build the response to AssetGroupSighting GET
    def get_assets(self):
        assets = []
        if not self.config.get('assetReferences'):
            return assets
        for filename in self.config.get('assetReferences'):
            asset = self.asset_group.get_asset_for_file(filename)
            assert asset
            assets.append(asset)
        assets.sort(key=lambda ast: ast.guid)
        return assets

    def complete(self):
        for job_id in self.jobs:
            assert not self.jobs[job_id]['active']

        self.stage = AssetGroupSightingStage.processed
        with db.session.begin(subtransactions=True):
            db.session.merge(self)
        db.session.refresh(self)

    def job_complete(self, job_id_str):
        if job_id_str in self.jobs:
            self.jobs[job_id_str]['active'] = False

            outstanding_jobs = []
            for job in self.jobs.keys():
                if self.jobs[job]['active']:
                    outstanding_jobs.append(job)

            if len(outstanding_jobs) == 0:
                # All complete, updatedAssets now in same sate as other assets so no need to store anymore
                if 'updatedAssets' in self.config:
                    del self.config['updatedAssets']
                self.config = self.config
                self.stage = AssetGroupSightingStage.curation
                self.curation_start = datetime.utcnow()

            # This is necessary because we can only mark jobs as
            # modified if we assign to it
            self.jobs = self.jobs

            with db.session.begin(subtransactions=True):
                db.session.merge(self)
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
        for encounter_num in range(len(self.config['encounters'])):
            if self.config['encounters'][encounter_num]['guid'] == str(encounter_uuid):
                encounter_metadata = self.config['encounters'][encounter_num]
                break
        return encounter_metadata

    def add_annotation_to_encounter(self, encounter_guid, annot_guid):
        for encounter_num in range(len(self.config['encounters'])):
            encounter_metadata = self.config['encounters'][encounter_num]
            if encounter_metadata['guid'] == str(encounter_guid):
                if 'annotations' not in encounter_metadata.keys():
                    encounter_metadata['annotations'] = []
                if annot_guid not in encounter_metadata['annotations']:
                    encounter_metadata['annotations'].append(annot_guid)

    def remove_annotation_from_encounter(self, encounter_guid, annot_guid):
        for encounter_num in range(len(self.config['encounters'])):
            encounter_metadata = self.config['encounters'][encounter_num]
            if encounter_metadata['guid'] == str(encounter_guid):
                if (
                    'annotations' in encounter_metadata.keys()
                    and annot_guid in encounter_metadata['annotations']
                ):
                    breakpoint()
                    self.config['encounters'][encounter_num]['annotations'].remove(
                        annot_guid
                    )

    def remove_annotation(self, annot_guid):
        for encounter_num in range(len(self.config['encounters'])):
            encounter_metadata = self.config['encounters'][encounter_num]
            if (
                'annotations' in encounter_metadata.keys()
                and annot_guid in encounter_metadata['annotations']
            ):
                self.config['encounters'][encounter_num]['annotations'].remove(annot_guid)

    def get_id_configs(self):
        return self.config.get('idConfigs', [])


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
    def ensure_remote_delay(cls, asset_group):
        from .tasks import ensure_remote

        ensure_remote.delay(str(asset_group.guid))

    def git_push_delay(self):
        from .tasks import git_push

        git_push.delay(str(self.guid))

    def delete_remote_delay(self):
        from .tasks import delete_remote

        delete_remote.delay(str(self.guid))

    def git_commit_metadata_hook(self, local_store_metadata):
        if 'frontend_sightings_data' not in local_store_metadata and self.config:
            metadata_request = self.config
            metadata_request['sightings'] = []
            for sighting in self.asset_group_sightings:
                metadata_request['sightings'].append(sighting.config)
            local_store_metadata['frontend_sightings_data'] = metadata_request

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

        # Store the metadata in the AssetGroup but not the sightings, that is stored on the AssetGroupSightings
        self.config = dict(metadata.request)
        del self.config['sightings']

        for sighting_meta in metadata.request['sightings']:
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

        # Store the metadata in the AssetGroup but not the sightings, that is stored on the AssetGroupSightings
        self.config = dict(metadata.request)
        del self.config['sightings']

        description = 'Adding Creation metadata'
        if metadata.description != '':
            description = metadata.description
        self.git_commit(description)

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
