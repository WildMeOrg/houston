# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""
import datetime  # NOQA
import enum
import logging
import uuid

from flask import current_app, url_for

import app.extensions.logging as AuditLog
from app.extensions import FeatherModel, HoustonModel, db
from app.modules.annotations.models import Annotation
from app.modules.encounters.models import Encounter
from app.modules.individuals.models import Individual
from app.utils import HoustonException
from flask_restx_patched._http import HTTPStatus

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

MAX_IDENTIFICATION_ATTEMPTS = 10


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
    # Content = jobId : {
    #                'algorithm': algorithm,
    #                'annotation': str(annotation_uuid),
    #                'active': boolean,
    #                'success': boolean, Only present once active is False
    #                'failure_reason': freeform text
    #                'result': processed ID result data from Sage, only present if active is False and success is True
    #           }
    jobs = db.Column(db.JSON, default=lambda: {}, nullable=True)

    # Used for managing retries. The above is for jobs that were successfully created, this is for jobs that have
    # been requested but not yet created
    # Content =  [
    #     { 'configId': config, algorithmId': algorithm, 'annotation': str(annotation_uuid), num_tries: 1 },
    # ]
    job_configs = db.Column(db.JSON, default=lambda: [], nullable=True)

    asset_group_sighting_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group_sighting.guid'),
        index=True,
        nullable=True,
    )
    asset_group_sighting = db.relationship(
        'AssetGroupSighting', back_populates='sighting', uselist=False
    )

    id_configs = db.Column(db.JSON, nullable=True)

    name = db.Column(db.String(length=120), nullable=True)

    time_guid = db.Column(
        db.GUID, db.ForeignKey('complex_date_time.guid'), index=True, nullable=False
    )
    time = db.relationship('ComplexDateTime')

    encounters = db.relationship(
        'Encounter', back_populates='sighting', order_by='Encounter.guid'
    )
    unreviewed_start = db.Column(
        db.DateTime, index=True, default=datetime.datetime.utcnow, nullable=False
    )
    review_time = db.Column(
        db.DateTime, index=True, default=datetime.datetime.utcnow, nullable=False
    )

    progress_identification_guid = db.Column(
        db.GUID, db.ForeignKey('progress.guid'), index=False, nullable=True
    )

    progress_identification = db.relationship(
        'Progress',
        foreign_keys='Sighting.progress_identification_guid',
    )

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.sightings.schemas import ElasticsearchSightingSchema

        return ElasticsearchSightingSchema

    # when we index this sighting, lets (re-)index annotations
    def index_hook_obj(self, *args, **kwargs):
        kwargs['force'] = True
        for enc in self.encounters:
            for annot in enc.annotations:
                annot.index(*args, **kwargs)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'stage={self.stage}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def run_integrity(cls):
        result = {
            'no_encounters': [],
            'failed_sightings': [],
            'jobless_identifying_sightings': [],
        }

        # Sightings without encounters are an error that should never really happen
        result['no_encounters'] = [
            sight.guid
            for sight in Sighting.query.filter(~Sighting.encounters.any()).all()
        ]

        # As are failed sightings
        result['failed_sightings'] = [
            sight.guid
            for sight in (
                db.session.query(Sighting).filter(Sighting.stage == SightingStage.failed)
            ).all()
        ]

        # any sighting that has been identifying for over an hour looks suspicious. The only fault we know of at
        # the moment is if there are no jobs,
        an_hour_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        result['jobless_identifying_sightings'] = [
            sight.guid
            for sight in (
                db.session.query(Sighting)
                .filter(Sighting.stage == SightingStage.identification)
                .filter(Sighting.created < an_hour_ago)
                .filter(Sighting.jobs.is_(None))
            ).all()
        ]

        return result

    @classmethod
    def remove_all_empty(cls):
        # Sightings without encounters are an error that should never really happen
        for sighting in Sighting.query.filter(~Sighting.encounters.any()).all():
            sighting.delete_from_edm_and_houston()

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

    def get_location_id(self):
        return self.get_edm_data_field('locationId')

    def get_location_id_value(self):
        location_id_value = None
        location_id = self.get_location_id()

        from app.modules.site_settings.models import Regions

        try:
            regions = Regions()
        except ValueError as e:
            if str(e) == 'no region data available':
                log.warning(str(e))
                return None
            raise
        region_data = regions.find(location_id, id_only=False)
        if region_data:
            location_id_value = region_data[0].get('name', location_id)

        return location_id_value

    def get_locality(self):
        return self.get_edm_data_field('verbatimLocality')

    def get_taxonomy_guid(self):
        return self.get_edm_data_field('taxonomy')

    def get_comments(self):
        return self.get_edm_data_field('comments')

    def get_custom_fields(self):
        return self.get_edm_data_field('customFields')

    def init_progress_identification(self, overwrite=False):
        from app.modules.progress.models import Progress

        if self.progress_identification:
            if overwrite:
                self.progress_identification.cancel()
            else:
                log.warning(
                    'Sighting %r already has a progress identification %r'
                    % (
                        self,
                        self.progress_identification,
                    )
                )
                return

        progress = Progress(
            description='Sage identification for Sighting {!r}'.format(self.guid)
        )
        with db.session.begin():
            db.session.add(progress)

        with db.session.begin():
            self.progress_identification_guid = progress.guid
            db.session.merge(self)

        # Assign the parent's progress
        if self.asset_group_sighting:
            self.asset_group_sighting.init_progress_identification()  # Ensure initialized

            if (
                self.progress_identification
                and self.asset_group_sighting.progress_identification
            ):
                with db.session.begin():
                    self.progress_identification.parent_guid = (
                        self.asset_group_sighting.progress_identification.guid
                    )
                db.session.merge(self.progress_identification)

        db.session.refresh(self)

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
        return user is not None and user in self.get_owners()

    def set_stage(self, stage, refresh=True):
        with db.session.begin(subtransactions=True):
            self.stage = stage
            db.session.merge(self)
        if refresh:
            db.session.refresh(self)

    def get_encounters(self):
        return self.encounters

    def add_encounter(self, encounter):
        if encounter not in self.encounters:
            self.encounters.append(encounter)

    def reviewed(self):
        ret_val = False
        if self.stage == SightingStage.un_reviewed:
            self.set_stage(SightingStage.processed)
            self.review_time = datetime.datetime.utcnow()
            ret_val = True
        return ret_val

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

    # truly unsure if these sets might always be the same, so.....
    def get_assets(self):
        return [ref.asset for ref in self.sighting_assets]

    def get_encounter_assets(self):
        assets = set()
        for enc in self.encounters:
            assets.update(enc.get_assets())
        return assets

    def get_all_assets(self):
        assets = set(self.get_assets())
        assets.update(self.get_encounter_assets())
        return assets

    def get_annotations(self):
        annots = []
        for enc in self.encounters:
            if enc.annotations:
                annots += enc.annotations
        return annots

    def add_asset(self, asset):
        if asset not in self.get_assets():
            with db.session.begin(subtransactions=True):
                self.add_asset_in_context(asset)

    @classmethod
    def get_unsupported_fields(cls, fields):
        from app.modules.site_settings.models import SiteSetting

        from .parameters import PatchSightingDetailsParameters

        unsupported_fields = []

        path_choices = PatchSightingDetailsParameters.PATH_CHOICES
        custom_fields = SiteSetting.get_value('site.custom.customFields.Sighting')
        for field in fields:
            if f'/{field}' in path_choices:
                # supported
                continue
            if custom_fields and field in custom_fields:
                # supported
                continue
            unsupported_fields.append(field)
        return unsupported_fields

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

    # this is (from user perspective) when this "started", so really means
    #   AssetGroupSighting creation (if applicable)
    def get_submission_time(self):
        return (
            self.asset_group_sighting.created
            if self.asset_group_sighting
            else self.created
        )

    def get_submission_time_isoformat(self):
        return self.get_submission_time().isoformat() + 'Z'

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
        if self.jobs:
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

    # returns a getter for a given config field, allowing for casting and default vals
    @staticmethod
    def config_field_getter(field_name, default=None, cast=None):
        def getter(self):
            value = (
                self.asset_group_sighting
                and self.asset_group_sighting.get_config_field(field_name)
            )
            if cast is not None and value:
                value = cast(value)
            return value or default

        return getter

    def is_migrated_data(self):
        return self.asset_group_sighting_guid is None

    def get_pipeline_status(self):
        db.session.refresh(self)
        status = {
            'preparation': self._get_pipeline_status_preparation(),
            'detection': self._get_pipeline_status_detection(),
            'curation': self._get_pipeline_status_curation(),
            'identification': self._get_pipeline_status_identification(),
            'now': datetime.datetime.utcnow().isoformat(),
            'stage': self.stage,
            'migrated': self.is_migrated_data(),
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

    # this piggybacks off of AssetGroupSighting.... *if* we have one!
    #   otherwise we assume we are migrated and kinda fake it
    def _get_pipeline_status_preparation(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting._get_pipeline_status_preparation()
        # migration "approximation"
        status = {
            'skipped': False,
            'start': None,
            'end': None,
            'message': None,
            'inProgress': False,
            'complete': True,
            'failed': False,
            'eta': None,
            'ahead': None,
            'steps': 1,
            'stepsComplete': 1,
            'progress': 1.0,
        }
        return status

    # this piggybacks off of AssetGroupSighting.... *if* we have one!
    #   otherwise we assume we are migrated and kinda fake it
    def _get_pipeline_status_detection(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting._get_pipeline_status_detection()

        # this should/must mimic asset_group_sighting in terms of fields listed
        #   so keep in sync with that
        status = {
            'skipped': False,
            'start': None,
            'end': None,
            'inProgress': False,
            'complete': True,  # just going to assume it ran
            'failed': False,
            'message': None,
            'eta': None,
            'ahead': None,
            'numModels': 1,  # seems true for migration
            'jobs': None,
            'numJobs': None,
            'numJobsActive': None,
            'numJobsFailed': None,
            'numAttempts': None,
            'numAttemptsMax': None,
            'numAssets': len(self.get_encounter_assets()),
            'numAnnotations': len(self.get_annotations()),
            'steps': 1,
            'stepsComplete': 1,
            'progress': 1.0,
            '_note': 'migrated sighting; detection status fabricated',
        }
        return status

    def _get_pipeline_status_curation(self):

        if self.asset_group_sighting:
            status = self.asset_group_sighting._get_pipeline_status_curation()
        else:
            status = {
                '_note': 'migrated sighting; curation status fabricated',
                'skipped': False,
                'start': None,
                'end': None,
                'inProgress': False,
                'complete': False,
                'failed': False,
                'progress': 0.0,
            }
            # setting only fields that would be set already if there were an AGS
            if len(self.get_assets()) < 1:
                status['skipped'] = True

            # The curation stage starts when manual annotation OR detection adds the first annotation to the asset group sighting.
            annotations = self.get_annotations()
            if annotations and len(annotations) > 1:
                times = [ann.created for ann in annotations]
                first_time = min(times)
                status['start'] = first_time.isoformat() + 'Z'
            else:
                status['start'] = self.created.isoformat() + 'Z'

        # Sightings have all finished the curation stage
        status['inProgress'] = False
        status['complete'] = True
        status['end'] = self.created.isoformat() + 'Z'
        status['progress'] = 1.0
        return status

    def _get_pipeline_status_identification(self):
        from app.utils import datetime_string_to_isoformat

        annots = self.get_annotations()
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
            # these are only based on 0th id_config (all that we have for mvp)
            'matchingSetQueryPassed': None,
            'matchingSetQueryUsed': None,
            # this is only based on 0th annotation (so is approximate)
            # 'matchingSetSize': None,   # dropped now cuz its expensive
            'numAttempts': None,
            'numAttemptsMax': None,
            'idConfigs': None,
            'numAssets': len(self.get_encounter_assets()),
            'numAnnotations': len(annots),
            'steps': 0,
            'stepsComplete': 0,
            'progress': None,
        }

        status['idConfigs'] = self.get_id_configs()
        if status['idConfigs']:
            # TODO not entirely true... i think.  as this can be passed via api (single annot)
            status['matchingSetQueryPassed'] = status['idConfigs'][0].get('matching_set')

        if not self.is_migrated_data():
            # seems irrelevant for migrated
            if annots:
                # too expensive
                # status['matchingSetSize'] = len(annots[0].get_matching_set(load=False))
                if status['matchingSetQueryPassed']:
                    status['matchingSetQueryUsed'] = annots[0].resolve_matching_set_query(
                        status['matchingSetQueryPassed']
                    )
                else:
                    status['matchingSetQueryUsed'] = annots[
                        0
                    ].get_matching_set_default_query()
        else:
            status['_note'] = 'migrated data; status should be interpretted in context'

        if self.stage == SightingStage.identification:
            status['inProgress'] = True
            status['steps'] += 1

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
                # we sh/could toggle active if this shows failure
                ss = None
                try:
                    # disabling for now as we are going to start using Progress soon
                    # ss = self.get_sage_job_status(job_id)
                    pass
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

    @classmethod
    def check_jobs(cls):
        pass

    #     # get scheduled celery tasks only once and use for all AGS
    #     from app.utils import get_celery_tasks_scheduled

    #     all_scheduled = get_celery_tasks_scheduled(
    #         'app.modules.sightings.tasks.send_identification'
    #     ) + get_celery_tasks_scheduled(
    #         'app.modules.sightings.tasks.send_all_identification'
    #     )
    #     for (sighting_guid,) in Sighting.query.filter(
    #         Sighting.stage == SightingStage.identification
    #     ).values(Sighting.guid):
    #         Sighting.query.get(sighting_guid).check_all_job_status(all_scheduled)

    # def check_all_job_status(self, all_scheduled):
    #     jobs = self.jobs

    #     if not jobs:
    #         # Somewhat arbitrary limit of at least 10 minutes after creation.
    #         if (
    #             not all_scheduled
    #             and datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    #             > self.created
    #         ):
    #             # TODO it would be nice to know if the scheduled tasks were for other Sightings than this one
    #             # but at the moment, it's not clear how we could detect this
    #             log.warning(
    #                 f'{self.guid} is identifying but no identification jobs are running, '
    #                 'assuming Celery error and starting them all again'
    #             )
    #         self.send_all_identification()
    #         return

    #     for job_id in jobs.keys():
    #         job = jobs[job_id]
    #         if job['active']:
    #             current_app.sage.request_passthrough_result(
    #                 'engine.result', 'get', {}, job
    #             )
    #             # TODO Process response DEX-335
    #             # TODO If UTC Start more than {arbitrary limit} ago.... do something

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

        for sighting in Sighting.query.all():
            jobs.extend(sighting.get_job_debug(annotation_id=None, verbose=verbose))
        return jobs

    # Build up dict to print out status (calling function chooses what to collect and print)
    def get_job_debug(self, annotation_id=None, verbose=True):

        details = []
        if not self.jobs:
            return details
        for job_id in self.jobs.keys():
            if annotation_id and str(annotation_id) != self.jobs[job_id]['annotation']:
                continue
            details.append(self.jobs[job_id])
            details[-1]['type'] = 'Sighting'
            details[-1]['object_guid'] = self.guid
            details[-1]['job_id'] = job_id

            if verbose:
                details[-1]['request'] = self.build_identification_request(
                    self.jobs[job_id].get('matching_set'),
                    self.jobs[job_id]['annotation'],
                    job_id,
                    self.jobs[job_id]['algorithm'],
                )
                try:
                    sage_data = current_app.sage.request_passthrough_result(
                        'engine.result', 'get', {}, job_id
                    )
                    # cm_dict is enormous and as we don't use it in Houston, don't print it as debug
                    if 'json_result' in sage_data and isinstance(
                        sage_data['json_result'], dict
                    ):
                        sage_data['json_result'].pop('cm_dict', None)
                    details[-1]['response'] = sage_data

                except HoustonException as ex:
                    # sage seems particularly flaky for getting the sighting data, if it fails, don't pass it back
                    details[-1][
                        'response'
                    ] = f'Failed to read data from Sage {ex.message}'

        return details

    def get_id_configs(self):
        return self.id_configs

    def get_jobs_json(self):
        job_data = []
        if not self.jobs:
            return job_data
        for job in self.jobs:
            from app.modules.sightings.schemas import DetailedSightingJobSchema

            schema = DetailedSightingJobSchema()
            this_job = schema.dump(self.jobs[job]).data
            this_job['job_id'] = job
            job_data.append(this_job)

        return job_data

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

    def get_debug_json(self):
        from app.modules.encounters.schemas import AugmentedEdmEncounterSchema

        result_json = self.get_edm_data_with_enc_schema(AugmentedEdmEncounterSchema())

        # Strip out old EDM ID
        result_json.pop('id', None)

        from .schemas import DebugSightingSchema

        sighting_schema = DebugSightingSchema()
        result_json.update(sighting_schema.dump(self).data)
        return result_json

    def get_detailed_json(self):
        from app.modules.encounters.schemas import AugmentedEdmEncounterSchema

        result_json = self.get_edm_data_with_enc_schema(AugmentedEdmEncounterSchema())
        # Strip out old EDM ID
        result_json.pop('id', None)

        from .schemas import AugmentedEdmSightingSchema

        sighting_schema = AugmentedEdmSightingSchema()
        result_json.update(sighting_schema.dump(self).data)
        return result_json

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
                    if edm_map[str(enc.guid)].get('version', 0) > enc.version:
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

    # specifically to pass to Sage, so we dress it up accordingly
    def get_matching_set_data(self, annotation, matching_set_config=None):
        from app.extensions.elapsed_time import ElapsedTime
        from app.extensions.sage import SAGE_UNKNOWN_NAME, to_sage_uuid

        timer = ElapsedTime()

        log.debug(
            f'sighting.get_matching_set_data(): sighting {self.guid} finding matching set for {annotation} using {matching_set_config}'
        )
        matching_set_annotations = annotation.get_matching_set(matching_set_config)
        log.debug(
            f'  found {len(matching_set_annotations)} annots in {timer.elapsed()} sec'
        )

        timer = ElapsedTime()
        matching_set_individual_uuids = []
        matching_set_annot_uuids = []
        unique_set = set()  # just to prevent duplication
        for annot in matching_set_annotations:
            # ideally the query on matching_set annots will exclude these, but in case someone got fancy:
            if not annot.content_guid:
                log.warning(f'skipping {annot} due to no content_guid')
                continue

            if annot.content_guid == annotation.content_guid:
                continue

            # this *does* assume the sighting exists due to elasticsearch constraints, in order to improve performance.
            #   it previously was this, which took longer as it needed to load two objects from db:
            #          if annot.encounter and annot.encounter.sighting:
            if annot.encounter_guid and annot.content_guid not in unique_set:
                unique_set.add(annot.content_guid)

                individual_guid = annot.get_individual_guid()
                if individual_guid:
                    individual_guid = str(individual_guid)
                else:
                    # Use Sage default value
                    individual_guid = SAGE_UNKNOWN_NAME

                matching_set_annot_uuids.append(annot.content_guid)
                matching_set_individual_uuids.append(individual_guid)

        # Ensure that the annotation we are querying on is in the database list as well
        matching_set_annot_uuids = list(
            map(to_sage_uuid, sorted(set(matching_set_annot_uuids)))
        )
        log.debug(
            f'sighting.get_matching_set_data(): [{timer.elapsed()} sec] Built matching set individuals {matching_set_individual_uuids}, '
            f'annots {matching_set_annot_uuids} for Annot {annotation} on {self}'
        )
        return matching_set_individual_uuids, matching_set_annot_uuids

    def build_identification_request(
        self,
        annotation,
        matching_set_config,
        job_uuid,
        algorithm,
    ):
        from app.extensions.sage import SAGE_UNKNOWN_NAME

        debug_context = f'Sighting:{self.guid}, Annot:{annotation}, algorithm:{algorithm}'
        (
            matching_set_individual_uuids,
            matching_set_annot_uuids,
        ) = self.get_matching_set_data(annotation, matching_set_config)

        assert len(matching_set_individual_uuids) == len(matching_set_annot_uuids)

        # Sage doesn't support an empty database set, so if no annotations, don't send the request
        if len(matching_set_individual_uuids) == 0:
            log.debug(
                f'{debug_context} No matching individuals, don\'t send request to sage'
            )
            return {}

        from app.extensions.sage import to_sage_uuid
        from app.modules.ia_config_reader import IaConfig

        callback_url = url_for(
            'api.sightings_sighting_sage_identified',
            sighting_guid=str(self.guid),
            job_guid=str(job_uuid),
            _external=True,
        )
        ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))
        try:
            id_config_dict = ia_config_reader.get(f'_identifiers.{algorithm}')['sage']
        except KeyError:
            raise HoustonException(log, f'failed to find {algorithm}', obj=self)

        id_request = {
            'jobid': str(job_uuid),
            'callback_url': f'houston+{callback_url}',
            # 'callback_detailed': True,
            'matching_state_list': [],
            'query_annot_name_list': [SAGE_UNKNOWN_NAME],
            'query_annot_uuid_list': [
                to_sage_uuid(annotation.content_guid),
            ],
            'database_annot_name_list': matching_set_individual_uuids,
            'database_annot_uuid_list': matching_set_annot_uuids,
        }
        id_request = id_request | id_config_dict

        log.debug(f'{debug_context} Built ID message for sage :{id_request}')
        return id_request

    def send_all_identification(self):

        self.init_progress_identification()

        # Annotation.sync_all_with_sage(ensure=True)

        sighting_guid = str(self.guid)
        num_jobs = 0
        # Once we support multiple IA configs and algorithms, the number of jobs is going to grow....rapidly
        #  also: once we have > 1 config, some annot-level checks will be redundant (e.g. matching_set) so may
        #    require a rethink on how these loops are nested
        annotation_guids = (
            Annotation.query.join(Annotation.encounter)
            .join(Encounter.sighting)
            .filter(Sighting.guid == sighting_guid)
            .values(Annotation.guid)
        )
        annotation_guids = sorted(
            {annotation_guid[0] for annotation_guid in annotation_guids}
        )
        for annotation_guid in annotation_guids:
            annot = Annotation.query.get(annotation_guid)

            annot.sync_with_sage(ensure=True)

            annot.init_progress_identification(
                parent=self.progress_identification, overwrite=True
            )

            if annot.progress_identification:
                # Set the status to healthy and 0%
                annot.progress_identification = annot.progress_identification.config()

            for config_id in range(len(self.id_configs)):
                conf = self.id_configs[config_id]
                matching_set_query = conf.get('matching_set', None)
                # load=False should get us this response quickly, cuz we just want a count
                matching_set = annot.get_matching_set(matching_set_query, load=False)

                if not matching_set:
                    skip_message = f'Sighting {self.guid} send_all_identification annot {annot} {config_id} no matching set'
                    log.info(skip_message)
                    if annot.progress_identification:
                        annot.progress_identification.skip(skip_message)
                    continue
                for algorithm_id in range(len(conf['algorithms'])):
                    if self._has_active_jobs(str(annot.guid), config_id, algorithm_id):
                        skip_message = f'Sighting {self.guid} send_all_identification annot {annot} {config_id}{algorithm_id} has active jobs'
                        log.info(skip_message)
                        if annot.progress_identification:
                            annot.progress_identification.skip(skip_message)
                        continue

                    num_jobs += 1

                    if annot.progress_identification:
                        annot.progress_identification.set(1)

                    self.send_identification(annot, config_id, algorithm_id)

        if num_jobs > 0:
            message = (
                f'Started Identification for Sighting:{self.guid} using {num_jobs} jobs'
            )
            AuditLog.audit_log_object(log, self, message)
        else:
            self.set_stage(SightingStage.un_reviewed)
            message = f'Sighting {self.guid} un-reviewed, identification not needed or not possible (jobs=0)'
            AuditLog.audit_log_object(log, self, message)
            with db.session.begin(subtransactions=True):
                db.session.merge(self)

    def send_identification(
        self,
        annotation,
        config_id,
        algorithm_id,
        matching_set_query=None,
    ):
        from app.extensions.sage import from_sage_uuid

        if annotation.progress_identification:
            annotation.progress_identification.set(2)

        if not self.id_configs:
            message = 'send_identification called without id_configs'
            log.warning('send_identification called without id_configs')
            self.set_stage(SightingStage.failed)
            if annotation.progress_identification:
                annotation.progress_identification.fail(message)
            return

        if annotation.progress_identification:
            annotation.progress_identification.set(3)

        try:
            # Message construction has to be in the task as the jobId must be unique
            job_uuid = uuid.uuid4()
            job_uuid_str = str(job_uuid)

            algorithm = self._get_algorithm_name(config_id, algorithm_id)
            debug_context = f'Sighting:{self.guid}, Annot:{annotation}, Ann content_guid:{annotation.content_guid} algorithm:{algorithm}, job:{job_uuid}'
            num_jobs = len(self.jobs)
            log.debug(f'{debug_context}, In send_identification, num jobs {num_jobs}')

            matching_set_query = matching_set_query or self.id_configs[config_id].get(
                'matching_set'
            )
            algorithm = self.id_configs[config_id]['algorithms'][algorithm_id]

            if annotation.progress_identification:
                annotation.progress_identification.set(4)

            with db.session.begin(subtransactions=True):
                self.jobs[job_uuid_str] = {
                    'matching_set': matching_set_query,
                    'algorithm': algorithm,
                    'annotation': str(annotation.guid),
                }

                if annotation.progress_identification:
                    annotation.progress_identification.set(5)

                id_request = self.build_identification_request(
                    annotation,
                    matching_set_query,
                    job_uuid,
                    algorithm,
                )
                if annotation.progress_identification:
                    annotation.progress_identification.set(6)

                if id_request != {}:
                    if annotation.progress_identification:
                        annotation.progress_identification.set(7)

                    # Ensure all annotations in the above request have been sent to Sage
                    query_sage_uuids = id_request.get('query_annot_uuid_list', [])
                    database_sage_uuids = id_request.get('database_annot_uuid_list', [])
                    query_sage_guids = set(map(from_sage_uuid, query_sage_uuids))
                    database_sage_guids = set(map(from_sage_uuid, database_sage_uuids))

                    requested_content_guids = query_sage_guids | database_sage_guids

                    if None in requested_content_guids:
                        requested_content_guids = list(requested_content_guids)
                        nulled = requested_content_guids.count(None)
                        raise HoustonException(
                            log,
                            'Tried to start an ID job with annotation content GUIDs that are None, missing: %r'
                            % (nulled,),
                            obj=self,
                        )

                    if annotation.progress_identification:
                        annotation.progress_identification.set(8)

                    local_content_guids = Annotation.query.with_entities(
                        Annotation.content_guid
                    ).all()
                    local_content_guids = {
                        item[0] for item in local_content_guids if item is not None
                    }

                    missing = requested_content_guids - local_content_guids
                    if len(missing) > 0:
                        raise HoustonException(
                            log,
                            'Tried to start an ID job with annotation content GUIDs that are not in the local Houston database, missing: %r'
                            % (missing,),
                            obj=self,
                        )

                    sage_uuids = current_app.sage.request_passthrough_result(
                        'annotation.list', 'get', target='sync'
                    )
                    sage_guids = {from_sage_uuid(uuid_) for uuid_ in sage_uuids}

                    missing = requested_content_guids - sage_guids
                    if len(missing) > 0:
                        raise HoustonException(
                            log,
                            'Tried to start an ID job with annotation content GUIDs that are not in the remote Sage database, missing: %r'
                            % (missing,),
                            obj=self,
                        )

                    search = database_sage_guids - query_sage_guids
                    if len(search) == 0:
                        raise HoustonException(
                            log,
                            'Tried to start an ID job with an empty database or with only the query annotation in the database, query: %r, database: %r'
                            % (
                                query_sage_guids,
                                database_sage_guids,
                            ),
                            obj=self,
                        )

                    if annotation.progress_identification:
                        annotation.progress_identification.set(9)

                    try:
                        sage_job_uuid = current_app.sage.request_passthrough_result(
                            'engine.identification', 'post', {'json': id_request}
                        )
                        sage_guid = uuid.UUID(sage_job_uuid)
                        assert sage_guid == job_uuid

                        if annotation.progress_identification:
                            annotation.progress_identification.set(10)

                        if annotation.progress_identification:
                            with db.session.begin(subtransactions=True):
                                annotation.progress_identification.sage_guid = sage_guid
                                db.session.merge(annotation.progress_identification)

                        log.info(f'{debug_context} Sent ID Request, creating job')
                        self.jobs[job_uuid_str]['active'] = True
                        self.jobs[job_uuid_str]['start'] = datetime.datetime.utcnow()

                    except HoustonException as ex:
                        sage_status_code = ex.get_val('sage_status_code', None)
                        if (
                            ex.status_code == HTTPStatus.SERVICE_UNAVAILABLE
                            or ex.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
                        ):
                            if (
                                self._get_attempts_for_config(
                                    str(annotation.guid), config_id, algorithm_id
                                )
                                < MAX_IDENTIFICATION_ATTEMPTS
                            ):
                                # Ensure Sage is completely up-to-date
                                Annotation.sync_all_with_sage(ensure=True)

                                log.warning(
                                    f'{debug_context} Sage Identification failed to start '
                                    f'code: {ex.status_code}, sage_status_code: {sage_status_code}, retrying'
                                )
                                self.send_annotation_for_identification_specific(
                                    annotation, config_id, algorithm_id, restart=False
                                )
                            else:
                                log.warning(
                                    f'{debug_context} Sage Identification failed to start '
                                    f'code: {ex.status_code}, sage_status_code: {sage_status_code}, giving up'
                                )
                                self.jobs[job_uuid_str]['active'] = False
                                self.jobs[job_uuid_str]['success'] = False
                                self.jobs[job_uuid_str][
                                    'failure_reason'
                                ] = 'too many retries'
                else:
                    self.jobs[job_uuid_str]['active'] = False
                    self.jobs[job_uuid_str]['success'] = False
                    self.jobs[job_uuid_str]['failure_reason'] = 'No ID request built'

                self.jobs = self.jobs

                db.session.merge(self)
            db.session.refresh(self)
        except Exception as ex:
            if annotation.progress_identification:
                annotation.progress_identification.fail(str(ex))
            raise

    # validate that the id response is a valid format and extract the data required from it
    def _parse_id_response(self, job_id_str, data):
        from app.extensions.sage import from_sage_uuid

        status = data.get('status', 'failed')
        result = {
            'scores_by_annotation': [],
            'scores_by_individual': [],
        }
        if status != 'completed':
            # This is not an exception as the message from Sage was valid
            error_msg = f'JobID {job_id_str} failed  message: {status}'
            AuditLog.backend_fault(log, error_msg, self)
            return status, result

        job_id_msg = data.get('jobid')
        if not job_id_msg:
            raise HoustonException(
                log, f'Must be a job id in the response {job_id_str}', obj=self
            )

        if job_id_msg != job_id_str:
            raise HoustonException(
                log,
                f'Job id in message {job_id_msg} must match job id in callback {job_id_str}',
                obj=self,
            )
        json_result = data.get('json_result')
        if not json_result:
            raise HoustonException(
                log, f'No json_result in the response for {job_id_str}', obj=self
            )

        query_annot_uuids = json_result.get('query_annot_uuid_list', [])
        if not query_annot_uuids:
            raise HoustonException(
                log,
                f'No query_annot_uuid_list in the json_result for {job_id_str}',
                obj=self,
            )

        if len(query_annot_uuids) != 1:
            raise HoustonException(
                log,
                f'Sage ID responded with {len(query_annot_uuids)} query_annots for {job_id_str}',
                obj=self,
            )

        sage_uuid = from_sage_uuid(query_annot_uuids[0])
        query_annots = Annotation.query.filter_by(content_guid=sage_uuid).all()
        if not query_annots:
            raise HoustonException(
                log,
                f'Sage ID response with unknown query annot uuid {sage_uuid} for job {job_id_str}',
                obj=self,
            )

        possible_annot_guids = [str(annot.guid) for annot in query_annots]
        job = self.jobs[job_id_str]
        if job['annotation'] not in possible_annot_guids:
            raise HoustonException(
                log,
                f'Sage ID response with invalid annot uuid {sage_uuid} for job {job_id_str}',
                obj=self,
            )

        # Now it's reasonably valid, let's extract the bits we need
        for target_annot_data in json_result['summary_annot']:
            sage_uuid = from_sage_uuid(target_annot_data['duuid'])
            target_annot = Annotation.query.filter_by(content_guid=sage_uuid).first()
            if not target_annot:
                raise HoustonException(
                    log,
                    f'Sage ID response with unknown target annot uuid {sage_uuid} for job {job_id_str}',
                    obj=self,
                )
            result['scores_by_annotation'].append(
                {str(target_annot.guid): target_annot_data['score']}
            )

        for target_annot_data in json_result['summary_name']:
            sage_uuid = from_sage_uuid(target_annot_data['duuid'])
            target_annot = Annotation.query.filter_by(content_guid=sage_uuid).first()
            if not target_annot:
                raise HoustonException(
                    log,
                    f'Sage ID response with unknown target annot uuid {sage_uuid} for job {job_id_str}',
                    obj=self,
                )
            result['scores_by_individual'].append(
                {str(target_annot.guid): target_annot_data['score']}
            )

        return status, result

    def identified(self, job_id, data):
        annotation = None

        try:
            job_id_str = str(job_id)
            if job_id_str not in self.jobs:
                raise HoustonException(log, f'job_id {job_id_str} not found', obj=self)
            job = self.jobs[job_id_str]
            algorithm = job['algorithm']
            annot_guid = job['annotation']
            debug_context = (
                f'Sighting:{self.guid}, Annot:{annot_guid}, algorithm:{algorithm}'
            )

            annotation = Annotation.query.get(annot_guid)
            if not annotation:
                raise HoustonException(
                    log, f'annotation {annot_guid} for {job_id_str} not found'
                )

            if annotation.progress_identification:
                annotation.progress_identification.set(90)

            status, result = self._parse_id_response(job_id_str, data)

            if annotation.progress_identification:
                annotation.progress_identification.set(91)

            description = ''
            try:
                from app.modules.ia_config_reader import IaConfig

                ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))
                id_config_dict = ia_config_reader.get(f'_identifiers.{algorithm}')
                assert id_config_dict
                frontend_data = id_config_dict.get('frontend', '')
                if frontend_data:
                    description = frontend_data.get('description', '')
            except KeyError:
                log.warning(f'{debug_context} failed to find {algorithm},')

            if annotation.progress_identification:
                annotation.progress_identification.set(92)

            log.info(
                f"{debug_context} Received successful response '{description}' from Sage for {job_id_str}"
            )
            log.debug(f'{debug_context} ID response stored result: {result}')

            # All good, mark job as finished
            with db.session.begin(subtransactions=True):
                job['active'] = False
                job['success'] = status == 'completed'
                job['result'] = result
                job['end'] = datetime.datetime.utcnow()

                if not self.any_jobs_active():
                    self.set_stage(SightingStage.un_reviewed)
                    self.unreviewed_start = datetime.datetime.utcnow()
                    message = f'Sighting {self.guid} all jobs completed'
                    AuditLog.audit_log_object(log, self, message)

                self.jobs = self.jobs
                db.session.merge(self)

            if annotation.progress_identification:
                annotation.progress_identification.set(95)

            # Ensure that the ID result is readable
            self.get_id_result()

            if annotation and annotation.progress_identification:
                annotation.progress_identification.set(100)
        except Exception as ex:
            if annotation and annotation.progress_identification:
                annotation.progress_identification.fail(str(ex))
            raise

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll Sage to see what's happening with this job, if it's ready to handle and we missed the
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
                'id_finish_time': str(q_annot_job['end']),
            }

        return t_annot, data

    # Helper to ensure that the required annot and individual data is present
    def _ensure_annot_data_in_response(self, annot, response):

        # will populate individual_first_name in next block to save a database hit
        individual_guid = annot.encounter.individual_guid if annot.encounter else None
        individual = Individual.query.get(individual_guid) if individual_guid else None

        if annot.guid not in response['annotation_data'].keys():
            encounter_location = (
                annot.encounter.get_location_id() if annot.encounter else None
            )
            # add annot data
            response['annotation_data'][str(annot.guid)] = {
                'viewpoint': annot.viewpoint,
                'encounter_location': encounter_location,
                'individual_guid': str(individual_guid),
                'image_url': annot.asset.get_image_url(),
                'asset_dimensions': annot.asset.get_dimensions(),
                'bounds': annot.bounds,
                'sighting_guid': self.guid,
                'sighting_time': self.get_time_isoformat_in_timezone(),
                'sighting_time_specificity': self.get_time_specificity(),
                'encounter_guid': annot.encounter.guid if annot.encounter else None,
                'asset_filename': annot.asset.filename,
                'individual_first_name': individual.get_first_name()
                if individual
                else None,
            }

        if (
            individual_guid is not None
            and annot.encounter.individual_guid not in response['individual_data'].keys()
        ):
            individual = Individual.query.get(individual_guid)
            assert individual

            # add individual data
            response['individual_data'][str(individual_guid)] = {
                'names': [
                    {
                        'guid': str(name.guid),
                        'context': name.context,
                        'value': name.value,
                    }
                    for name in individual.get_names()
                ],
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

            if not self.jobs:
                q_annot_jobs = []
            else:
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
            if not q_annot_job.get('result', False) or not q_annot_job.get(
                'success', False
            ):
                response['query_annotations'][-1]['status'] = 'failed'
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

    def set_asset_group_sighting(self, ags):
        self.asset_group_sighting = ags
        self.id_configs = ags.get_id_configs()
        if not self.id_configs:
            # If no configs passed by the user, use the first one from the IA Config
            from app.modules.ia_config_reader import IaConfig

            ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))

            identifiers = ia_config_reader.get('_identifiers')
            self.id_configs = [{'algorithms': [list(identifiers.keys())[0]]}]

    def validate_id_configs(self):
        num_configs = len(self.id_configs)
        if num_configs > 0:
            # Only one for MVP
            assert num_configs == 1
            for config_num in range(num_configs):
                config = self.id_configs[config_num]
                assert 'algorithms' in config
                # Only one for MVP
                assert len(config['algorithms']) == 1

    def ia_pipeline(self, foreground=None):

        self.init_progress_identification()

        if foreground is None:
            foreground = current_app.testing

        assert self.stage == SightingStage.identification, self.stage
        self.validate_id_configs()

        if foreground:
            self.send_all_identification()
            promise = None
        else:
            from .tasks import send_all_identification

            promise = send_all_identification.delay(str(self.guid))

            log.info(f'Starting Identification for Sighting:{self.guid} in celery')

        if self.progress_identification and promise:
            with db.session.begin():
                self.progress_identification.celery_guid = promise.id
                db.session.merge(self.progress_identification)

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

    # this iterates over configs and algorithms
    # note: self.validate_id_configs() should be called before this (once)
    def send_annotation_for_identification(
        self, annotation, matching_set_query=None, foreground=None
    ):
        if foreground is None:
            foreground = current_app.testing

        num_jobs = 0
        annotation_guid = str(annotation.guid)
        for config_id in range(len(self.id_configs)):
            # note: we could test matching_set here and prevent duplicate testing within specific()
            #  but we would have to be careful of code calling specific *directly*
            for algorithm_id in range(len(self.id_configs[config_id]['algorithms'])):
                if self.send_annotation_for_identification_specific(
                    Annotation.query.get(annotation_guid),
                    config_id,
                    algorithm_id,
                    matching_set_query,
                    foreground=foreground,
                ):
                    num_jobs += 1
        return num_jobs

    # see also send_annotation_for_identification() above
    def send_annotation_for_identification_specific(
        self,
        annotation,
        config_id,
        algorithm_id,
        matching_set_query=None,
        restart=True,
        foreground=None,
    ):
        from app.extensions import elasticsearch as es

        if foreground is None:
            foreground = current_app.testing

        algorithm = self._get_algorithm_name(config_id, algorithm_id)
        debug_context = (
            f'Sighting:{self.guid}, Annot:{annotation.guid}, algorithm:{algorithm}'
        )
        log.debug(
            f'{debug_context} Sending ID for '
            f'sage_annot:{annotation.content_guid} enc:{annotation.encounter_guid}'
        )
        assert self.id_configs and 0 <= config_id < len(self.id_configs)
        if not annotation.content_guid or not annotation.encounter_guid:
            log.warning(
                f'{debug_context} Skipping {annotation} due to lack of content_guid or encounter'
            )
            return False

        # force this to be up-to-date in index
        with es.session.begin(blocking=True):
            annotation.index()

        matching_set_query = matching_set_query or self.id_configs[config_id].get(
            'matching_set'
        )
        # load=False should get us this response quickly, cuz we just want a count
        matching_set = annotation.get_matching_set(matching_set_query, load=False)
        if not matching_set:
            log.info(
                f'{debug_context} Skipping {annotation.guid} due to empty matching set'
            )
            return False

        if self._has_active_jobs(str(annotation.guid), config_id, algorithm_id):
            log.info(
                f'{debug_context} Skipping {annotation.guid} as already an active job for {algorithm_id}'
            )
            return False

        log.debug(
            f'{debug_context} Queueing up ID job: '
            f'matching_set size={len(matching_set)} algo {algorithm_id}'
        )

        self.init_progress_identification()

        annotation.init_progress_identification(parent=self.progress_identification)

        if annotation.progress_identification:
            # Set the status to healthy and 0%
            annotation.progress_identification = (
                annotation.progress_identification.config()
            )

        if foreground:
            self.send_identification(
                annotation,
                config_id,
                algorithm_id,
                matching_set_query,
            )
            promise = None
        else:
            from .tasks import send_identification

            promise = send_identification.delay(
                str(self.guid),
                str(annotation.guid),
                config_id,
                algorithm_id,
                matching_set_query,
            )

        if self.progress_identification and promise:
            if annotation.progress_identification:
                annotation.progress_identification.set(1)
            with db.session.begin():
                self.progress_identification.celery_guid = promise.id
                db.session.merge(self.progress_identification)

        # store that we sent it (handles retry counts)
        self._update_job_config(str(annotation.guid), config_id, algorithm_id, restart)
        return True

    def _get_job_config(self, annotation_guid_str, config_id, algorithm_id):
        for job_cnf in self.job_configs:
            # { 'configId': config, 'algorithmId': algorithm, 'annotation': str(annotation_uuid), 'num_tries': 1 }
            if (
                job_cnf['annotation'] == annotation_guid_str
                and job_cnf['configId'] == config_id
                and job_cnf['algorithmId'] == algorithm_id
            ):
                return job_cnf
            return {}

    def _update_job_config(self, annotation_guid_str, config_id, algorithm_id, restart):
        job_cnf = self._get_job_config(annotation_guid_str, config_id, algorithm_id)
        if job_cnf:
            job_cnf['num_tries'] = 1 if restart else job_cnf['num_tries'] + 1
        else:
            # doesn't exist, need to create a new one
            new_cnf = {
                'configId': config_id,
                'algorithmId': algorithm_id,
                'annotation': annotation_guid_str,
                'num_tries': 1,
            }
            self.job_configs.append(new_cnf)

        self.job_configs = self.job_configs
        with db.session.begin(subtransactions=True):
            db.session.merge(self)

    def _get_attempts_for_config(self, annotation_guid_str, config_id, algorithm_id):
        job_cnf = self._get_job_config(annotation_guid_str, config_id, algorithm_id)
        if job_cnf:
            return job_cnf['num_tries']
        else:
            return 0

    def _has_active_jobs(self, annotation_guid_str, config_id, algorithm_id):
        for job in self.jobs:
            if (
                self.jobs[job]['algorithm']
                == self._get_algorithm_name(config_id, algorithm_id)
                and self.jobs[job]['annotation'] == annotation_guid_str
            ):
                return self.jobs[job]['active']
        return False

    def _get_algorithm_name(self, config_id, algorithm_id):
        return self.id_configs[config_id]['algorithms'][algorithm_id]
