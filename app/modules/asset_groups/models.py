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
from http import HTTPStatus

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
    curation_start = db.Column(db.DateTime, index=True, default=None, nullable=True)
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

    def user_can_access(self, user):
        if not user.is_researcher:
            # even owners, if they are not researchers, cannot access their own asset group sightings
            return False
        if self.user_is_owner(user):
            return True
        # A Researcher can control any anonymous or contributors AGS but not another researchers
        if not self.asset_group.owner.is_researcher:
            return True

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
            self.init_progress_detection()  # ensure we have one
            self.progress_detection.skip('No assets were submitted')
            # All encounters need to be allocated a pseudo guid. This is done by the
            # begin_ia_pipeline if there are assets
            for encounter_num in range(len(self.sighting_config['encounters'])):
                if 'guid' not in self.sighting_config['encounters'][encounter_num]:
                    with db.session.begin(subtransactions=True):
                        self.sighting_config['encounters'][encounter_num]['guid'] = str(
                            uuid.uuid4()
                        )
                        # sighting_config is actually an alias, need to rewrite the top level DB item
                        self.config = self.config
                        db.session.merge(self)
                        db.session.refresh(self)
            self.set_stage(AssetGroupSightingStage.curation)
            self.commit()

        elif len(self.detection_configs) == 1 and (
            not self.detection_configs[0] or self.detection_configs[0] == 'None'
        ):
            self.init_progress_detection()  # ensure we have one
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

        if 'time' not in self.sighting_config:
            raise HoustonException(
                log,
                'Must have time/timeSpecificity values',
                obj=self,
            )

        from app.modules.complex_date_time.models import ComplexDateTime
        from app.modules.site_settings.helpers import SiteSettingCustomFields

        try:
            # will raise ValueError if data no good
            time = ComplexDateTime.from_data(self.sighting_config)
        except ValueError as ve:
            raise HoustonException(
                log,
                f'Problem with sighting time/timeSpecificity values: {str(ve)}',
                obj=self,
            )

        cf_dict = self.sighting_config.get('customFields', {})
        invalid = {}
        for cfd_id in cf_dict:
            defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
            deser_value = SiteSettingCustomFields.deserialize_value(defn, cf_dict[cfd_id])
            valid = SiteSettingCustomFields.is_valid_value_for_class(
                'Sighting', cfd_id, deser_value
            )
            if not valid:
                invalid[cfd_id] = cf_dict[cfd_id]
        if invalid:
            raise HoustonException(
                log,
                f'Problem with customFields value(s): {invalid}',
                obj=self,
            )

        sighting = Sighting(
            # asset_group_sighting=self,  -- see note below
            name=self.sighting_config.get('name', ''),
            stage=SightingStage.identification,
            location_guid=self.sighting_config.get('locationId'),
            verbatim_locality=self.sighting_config.get('verbatimLocality'),
            decimal_latitude=self.sighting_config.get('decimalLatitude'),
            decimal_longitude=self.sighting_config.get('decimalLongitude'),
            custom_fields=cf_dict,
            time=time,
        )

        with db.session.begin(subtransactions=True):
            db.session.add(sighting)

        # Add the assets for all of the encounters to the created sighting object
        for reference in self.sighting_config.get('assetReferences', []):
            asset = self.asset_group.get_asset_for_file(reference)
            assert asset
            sighting.add_asset(asset)

        for encounter_num in range(len(self.sighting_config['encounters'])):
            req_data = self.sighting_config['encounters'][encounter_num]
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
                try:
                    # will raise ValueError if data no good
                    if 'time' in req_data:
                        time = ComplexDateTime.from_data(req_data)
                    else:
                        time = None
                except ValueError as ve:
                    raise HoustonException(
                        log,
                        f'Problem with sighting time/timeSpecificity values: {str(ve)}',
                        obj=self,
                    )
                assert 'guid' in req_data
                new_encounter = Encounter(
                    individual=individual,
                    owner_guid=owner_guid,
                    asset_group_sighting_encounter_guid=req_data['guid'],
                    submitter_guid=self.asset_group.submitter_guid,
                    decimal_latitude=req_data.get('decimalLatitude'),
                    decimal_longitude=req_data.get('decimalLongitude'),
                    location_guid=req_data.get('locationId'),
                    taxonomy_guid=req_data.get('taxonomy'),
                    verbatim_locality=req_data.get('verbatimLocality'),
                    sex=req_data.get('sex'),
                    time=time,
                    custom_fields=req_data.get('customFields', {}),
                )

                if 'individualUuid' in req_data:
                    ind_guid = req_data['individualUuid']
                    individual = Individual.query.get(uuid.UUID(ind_guid))
                    if individual:
                        new_encounter.set_individual(individual)
                    else:
                        log.warning(
                            f'Individual with guid {ind_guid} not found for auto assignment to created encounter'
                        )

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
                sighting.delete()
                raise HoustonException(
                    log,
                    f'Problem with creating encounter [{encounter_num}]: {ex}'
                    f'{ex} on encounter {encounter_num}: enc={req_data}',
                )

        # This has to be done as the final step in the creation as the FE does not seem to wait for the commit
        # response but starts using the sighting as soon as it can be read from the AGS
        sighting.set_asset_group_sighting(self)

        # AssetGroupSighting is finished, all subsequent processing is on the Sighting
        self.complete()
        sighting.ia_pipeline()

        num_encounters = self.num_encounters()
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

    def get_detection_start_time(self):
        if self.detection_start:
            return self.detection_start.isoformat() + 'Z'
        return None

    def get_curation_start_time(self):
        if self.curation_start:
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
        enc_json['created'] = self.created
        enc_json['updated'] = self.updated
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

        enc_json['hasEdit'] = self.current_user_has_edit_permission()
        enc_json['hasView'] = self.current_user_has_view_permission()

        return enc_json

    def num_encounters(self):
        return (
            len(self.sighting_config['encounters'])
            if self.sighting_config
            and 'encounters' in self.sighting_config
            and isinstance(self.sighting_config['encounters'], list)
            else 0
        )

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
            'migrated': False,  # always false as AGS not created for migrated sightings
            'summary': {},
        }
        status['summary']['complete'] = (
            (status['preparation']['complete'] or status['preparation']['skipped'])
            and (status['detection']['complete'] or status['detection']['skipped'])
            and (status['curation']['complete'] or status['curation']['skipped'])
            and (
                status['identification']['complete']
                or status['identification']['skipped']
            )
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
        # no progress object, do the best we can?  assume complete  TODO is this sane?
        if not progress:
            return {
                'skipped': False,
                'inProgress': False,
                'failed': False,
                'complete': True,
                'message': 'missing Progress',
                'steps': 0,
                'stepsComplete': 0,
                'progress': 1,
                'start': self.get_submission_time_isoformat(),
                'end': self.get_submission_time_isoformat(),
                'eta': None,
                'ahead': None,
                'status': None,
                'description': None,
            }

        # much of this we just pass what Progress object has
        status = {
            # start with these false and set below
            'skipped': False,
            'inProgress': False,
            'failed': False,
            'complete': False,
            'message': progress.message,
            'steps': len(progress.steps) if progress.steps else 0,
            'stepsComplete': 0,  # TBD
            # using previously established 0.0-1.0 but maybe FE will want to swtich to 0-100
            'progress': progress.percentage / 100,
            'start': progress.created.isoformat() + 'Z',
            'end': None,
            'eta': progress.current_eta,
            'ahead': progress.ahead,
            'status': progress.status,
            'description': progress.description,
        }

        # hopefully this is decent priority/logic based on Progress class
        #   (it is used for other stages below)
        if progress.skipped:
            status['skipped'] = True
        elif progress.status == ProgressStatus.failed:
            status['failed'] = True
        elif progress.complete:
            status['complete'] = True
        elif (
            progress.status == ProgressStatus.created
            or progress.status == ProgressStatus.healthy
        ):
            status['inProgress'] = True
        # if it falls through, all False, thus "waiting"

        if progress.complete:
            status['end'] = progress.updated.isoformat() + 'Z'
        return status

    def _get_pipeline_status_detection(self):
        from app.modules.progress.models import ProgressStatus

        progress = self.progress_detection
        # no progress object, we assume it has not yet started
        if not progress:
            return {
                'skipped': False,
                'inProgress': False,
                'failed': False,
                'complete': False,
                'message': 'missing Progress',
                'steps': 0,
                'stepsComplete': 0,
                'progress': 0,
                'start': None,
                'end': None,
                'eta': None,
                'ahead': None,
                'status': None,
                'description': None,
            }

        status = {
            # start with these false and set below
            'skipped': False,
            'inProgress': False,
            'failed': False,
            'complete': False,
            'message': progress.message,
            'steps': len(progress.steps) if progress.steps else 0,
            'stepsComplete': 0,  # TBD
            'progress': progress.percentage / 100,
            'start': progress.created.isoformat() + 'Z',
            'end': None,
            'eta': progress.current_eta,
            'ahead': progress.ahead,
            'status': progress.status,
            'description': progress.description,
            # these are provisional and should only be used for debugging, not ui/ux
            # TODO i am not sure if this is the best count here, as there
            #   is config['updatedAssets'] which may actually need to be considered
            'numAssets': len(self.get_assets()),
            'numAnnotations': self.num_annotations(),
        }

        if progress.skipped:
            status['skipped'] = True
        elif progress.status == ProgressStatus.failed:
            status['failed'] = True
        elif progress.complete:
            status['complete'] = True
        elif (
            progress.status == ProgressStatus.created
            or progress.status == ProgressStatus.healthy
        ):
            status['inProgress'] = True
        # if it falls through, all False, thus "waiting"

        if progress.complete:
            status['end'] = progress.updated.isoformat() + 'Z'
        return status

    # this does not have a corresponding Progress, so we roll our own
    def _get_pipeline_status_curation(self):
        cur_start = self.get_curation_start_time()
        status = {
            # start with these false and set below
            'skipped': False,
            'inProgress': False,
            'failed': False,
            'complete': False,
            'message': None,
            'steps': 0,
            'stepsComplete': 0,
            'progress': 0,
            'start': cur_start,
            'end': None,
            'eta': None,
            'ahead': None,
            'status': None,
            'description': None,
        }

        # If there are no assets in an asset group sighting and prep is done, curation will be skipped.
        prep_status = self._get_pipeline_status_preparation()
        if len(self.get_assets()) < 1 and (
            prep_status['complete'] or prep_status['skipped']
        ):
            status['skipped'] = True
            return status

        # FIXME we may need to consider detection-not-run case below to adjust this accordingly
        # i think this is sufficient enough to know we have not started yet
        if not cur_start:
            return status

        # curation has completed if we have a sighting
        if len(self.sighting) > 0:
            status['complete'] = True
            status['progress'] = 1
            status['stepsComplete'] = 1
            status['steps'] = 1
            status['end'] = self.sighting[0].created.isoformat() + 'Z'
            return status

        # i think curation cannot fail, so the only thing left is to be inProgress
        #  note: possibly curation fails if the commit() does not produce a sighting; this may need exploration  TODO

        status['inProgress'] = True
        # this is the "Fisher progress constant" and on average it has zero error
        status['progress'] = 0.5

        # FIXME this will never get reached due to 'if not cur_start' above
        #   but leaving this here to consider using higher up here, but also taking into account that
        #   preparation may not even be finished yet and that logic should be included here as well
        #
        # detection may have been skipped and we need to infer
        if not status['start']:
            annotations = self.get_all_annotations()
            if annotations and len(annotations) > 1:
                first_annot_created = min(ann.created for ann in annotations)
                status['start'] = first_annot_created.isoformat() + 'Z'

        return status

    # this should be basically *nothing* since id doesnt happen until sighting, so lets
    #    hope that is what this yields
    def _get_pipeline_status_identification(self):
        from app.modules.progress.models import ProgressStatus

        progress = self.progress_identification
        # no progress object, we assume it has not yet started
        if not progress:
            return {
                'skipped': False,
                'inProgress': False,
                'failed': False,
                'complete': False,
                'message': 'missing Progress',
                'steps': 0,
                'stepsComplete': 0,
                'progress': 0,
                'start': None,
                'end': None,
                'eta': None,
                'ahead': None,
                'status': None,
                'description': None,
            }

        status = {
            # start with these false and set below
            'skipped': False,
            'inProgress': False,
            'failed': False,
            'complete': False,
            'message': progress.message,
            'steps': len(progress.steps) if progress.steps else 0,
            'stepsComplete': 0,  # TBD
            'progress': progress.percentage / 100,
            'start': progress.created.isoformat() + 'Z',
            'end': None,
            'eta': progress.current_eta,
            'ahead': progress.ahead,
            'status': progress.status,
            'description': progress.description,
        }

        if progress.skipped:
            status['skipped'] = True
        elif progress.status == ProgressStatus.failed:
            status['failed'] = True
        elif progress.complete:
            status['complete'] = True
        elif (
            progress.status == ProgressStatus.created
            or progress.status == ProgressStatus.healthy
        ):
            status['inProgress'] = True
        # if it falls through, all False, thus "waiting"

        if progress.complete:
            status['end'] = progress.updated.isoformat() + 'Z'
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
            # 'callback_detailed': True,
        }

        ia_config_reader = IaConfig()
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

            asset_sage_data.sort(
                key=lambda data: data[0]['__UUID__'] if data and data[0] else ''
            )
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
                        f'Started Detection job, on AssetGroupSighting {self.guid}, self.jobs={self.jobs}'
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
                    message = f'Sage Detection on AssetGroupSighting({self.guid}) Job{job_id} failed to start, '
                    message += f'code: {ex.status_code}, sage_status_code: {sage_status_code}, retrying'
                    AuditLog.audit_log_object_warning(log, self, message)
                    log.warning(message)
                    self.rerun_detection()
                else:
                    message = f'Sage Detection on AssetGroupSighting({self.guid}) Job{job_id} failed to start, '
                    message += f'code: {ex.status_code}, sage_status_code: {sage_status_code}, giving up'
                    AuditLog.audit_log_object_warning(log, self, message)
                    log.warning(message)

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
            if stage == AssetGroupSightingStage.detection:
                self.detection_start = datetime.datetime.utcnow()
            elif stage == AssetGroupSightingStage.curation:
                self.curation_start = datetime.datetime.utcnow()

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
                    annotation.index()

                for asset in assets:
                    db.session.merge(asset)

            db.session.refresh(self)

            self.job_complete(job_id)

            # if only one encounter, assign all annots to it
            if (
                self.stage == AssetGroupSightingStage.curation
                and 'encounters' in self.sighting_config
                and len(self.sighting_config['encounters']) == 1
            ):
                # Only one encounter, assign all annots to it
                enc_guid = self.sighting_config['encounters'][0]['guid']
                for annot in self.get_all_annotations():
                    self.add_annotation_to_encounter(enc_guid, str(annot.guid))

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
            if overwrite:
                self.progress_detection.cancel()
            else:
                message = f'Asset Group Sighting {self} already has a progress detection {self.progress_detection}'
                AuditLog.audit_log_object_warning(log, self, message)
                log.warning(message)
                return

        progress = Progress(
            description='Sage Detection for AssetGroupSighting {!r}'.format(self.guid)
        )
        with db.session.begin():
            db.session.add(progress)

        with db.session.begin():
            self.progress_detection_guid = progress.guid
            db.session.merge(self)

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
            if overwrite:
                self.progress_identification.cancel()
            else:
                message = f'Asset Group Sighting {self} already has a progress identification {self.progress_identification}'
                AuditLog.audit_log_object_warning(log, self, message)
                log.warning(message)
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

    def num_annotations(self):
        return len(self.get_all_annotations())

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

                # This is necessary because we can only mark jobs as
                # modified if we assign to it
                self.jobs = self.jobs

                db.session.merge(self)
            db.session.refresh(self)
        else:
            message = f'job_id {job_id} not found in AssetGroupSighting {self.guid}'
            AuditLog.audit_log_object_warning(log, self, message)
            log.warning(message)

    def delete(self):
        AuditLog.delete_object(log, self)
        if self.sighting:
            self.sighting[0].delete_cascade()

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
        # force db write
        self.config = self.config

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

    # per DEX-1246, ag.get_pipeline_status() *only* contains preparation stage
    def get_pipeline_status(self):
        db.session.refresh(self)
        status = {
            'preparation': self._get_pipeline_status_preparation(),
            'now': datetime.datetime.utcnow().isoformat(),
            # All non migrated groups have AGS, migrated groups just have assets, so use the presence of AGS to
            # set the migrated flag to True
            'migrated': len(self.asset_group_sightings) == 0
            # no summary cuz that seems weird with only one section?
        }
        return status

    def _get_pipeline_status_preparation(self):
        from app.modules.progress.models import ProgressStatus

        progress = self.progress_preparation
        if not progress:
            return {
                'skipped': False,
                'inProgress': False,
                'failed': False,
                'complete': True,
                'message': 'no Progress',
                'steps': 0,
                'stepsComplete': 0,
                'progress': 1,
                'start': self.created.isoformat() + 'Z',
                'end': self.created.isoformat() + 'Z',
                'eta': None,
                'ahead': None,
                'status': None,
                'description': None,
            }

        # much of this we just pass what Progress object has
        status = {
            # start with these false and set below
            'skipped': False,
            'inProgress': False,
            'failed': False,
            'complete': False,
            'message': progress.message,
            'steps': len(progress.steps) if progress.steps else 0,
            'stepsComplete': 0,  # TBD
            # using previously established 0.0-1.0 but maybe FE will want to swtich to 0-100
            'progress': progress.percentage / 100,
            'start': progress.created.isoformat() + 'Z',
            'end': None,
            'eta': progress.current_eta,
            'ahead': progress.ahead,
            'status': progress.status,
            'description': progress.description,
        }

        if progress.skipped:
            status['skipped'] = True
        elif progress.status == ProgressStatus.failed:
            status['failed'] = True
        elif progress.complete:
            status['complete'] = True
        elif (
            progress.status == ProgressStatus.created
            or progress.status == ProgressStatus.healthy
        ):
            status['inProgress'] = True
        # if it falls through, all False, thus "waiting"

        if progress.complete:
            status['end'] = progress.updated.isoformat() + 'Z'
        return status

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
