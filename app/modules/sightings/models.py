# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""
import enum
import logging
import uuid
from datetime import datetime  # NOQA
from flask import current_app, url_for
from flask_restx_patched._http import HTTPStatus

from app.extensions import FeatherModel, HoustonModel, db
from app.modules.annotations.models import Annotation
from app.modules.encounters.models import Encounter
from app.modules.individuals.models import Individual
from app.utils import HoustonException
import app.extensions.logging as AuditLog

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
    #                'annotation_sage_uuid': str(annotation_sage_uuid),
    #                'active': True,
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
        db.DateTime, index=True, default=datetime.utcnow, nullable=False
    )
    review_time = db.Column(
        db.DateTime, index=True, default=datetime.utcnow, nullable=False
    )

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.sightings.schemas import ElasticsearchSightingSchema

        return ElasticsearchSightingSchema

    # when we index this sighting, lets (re-)index annotations
    def index_hook_obj(self):
        for enc in self.encounters:
            for annot in enc.annotations:
                annot.index(force=True)

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
        import datetime

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

    def get_taxonomy_guid(self):
        return self.get_edm_data_field('taxonomy')

    def get_comments(self):
        return self.get_edm_data_field('comments')

    def get_custom_fields(self):
        return self.get_edm_data_field('customFields')

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

    def reviewed(self):
        ret_val = False
        if self.stage == SightingStage.un_reviewed:
            self.stage = SightingStage.processed
            self.review_time = datetime.utcnow()
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

    @classmethod
    def check_jobs(cls):
        # get scheduled celery tasks only once and use for all AGS
        from app.utils import get_celery_tasks_scheduled

        all_scheduled = get_celery_tasks_scheduled(
            'app.modules.sightings.tasks.send_identification'
        )
        for sighting in Sighting.query.filter(
            Sighting.stage == SightingStage.identification
        ).all():
            sighting.check_all_job_status(all_scheduled)

    def check_all_job_status(self, all_scheduled):
        jobs = self.jobs
        if not jobs:
            if not all_scheduled:
                # TODO it would be nice to know if the scheduled tasks were for other Sightings than this one
                # but at the moment, it's not clear how we could detect this
                log.warning(
                    f'{self.guid} is identifying but no identification jobs are running, '
                    'assuming Celery error and starting them all again'
                )
            self.ia_pipeline()
            return

        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                current_app.acm.request_passthrough_result(
                    'job.response', 'post', {}, job
                )
                # TODO Process response DEX-335
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
                    self.jobs[job_id]['annotation_sage_uuid'],
                    job_id,
                    self.jobs[job_id]['algorithm'],
                )
                try:
                    acm_data = current_app.acm.request_passthrough_result(
                        'job.response', 'post', {}, job_id
                    )
                    # cm_dict is enormous and as we don't use it in Houston, don't print it as debug
                    if 'json_result' in acm_data and isinstance(
                        acm_data['json_result'], dict
                    ):
                        acm_data['json_result'].pop('cm_dict', None)
                    details[-1]['response'] = acm_data

                except HoustonException as ex:
                    # acm seems particularly flaky for getting the sighting data, if it fails, don't pass it back
                    details[-1][
                        'response'
                    ] = f'Failed to read data from Sage {ex.message}'

        return details

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
    def get_matching_set_data(self, annotation_guid, matching_set_config=None):
        from app.extensions.acm import to_acm_uuid, default_acm_individual_uuid

        annotation = Annotation.query.get(annotation_guid)
        assert annotation
        log.debug(
            f'sighting {self} finding matching set for {annotation} using {matching_set_config}'
        )
        matching_set_annotations = annotation.get_matching_set(matching_set_config)

        matching_set_individual_uuids = []
        matching_set_annot_uuids = []
        for annot in matching_set_annotations:
            # ideally the query on matching_set annots will exclude these, but in case someone got fancy:
            if not annot.content_guid:
                log.warning(f'skipping {annot} due to no content_guid')
                continue
            if annot.encounter and annot.encounter.sighting:
                if annot.encounter.sighting.stage == SightingStage.processed:
                    acm_annot_uuid = to_acm_uuid(annot.content_guid)
                    if acm_annot_uuid not in matching_set_annot_uuids:
                        matching_set_annot_uuids.append(acm_annot_uuid)
                        individual_guid = annot.get_individual_guid()
                        if individual_guid:
                            individual_guid = str(individual_guid)
                        else:
                            # Use Sage default value
                            individual_guid = default_acm_individual_uuid()
                        matching_set_individual_uuids.append(individual_guid)

        log.debug(
            f'Built matching set individuals {matching_set_individual_uuids}, '
            f'annots {matching_set_annot_uuids}'
        )
        return matching_set_individual_uuids, matching_set_annot_uuids

    def build_identification_request(
        self,
        matching_set_config,
        annotation_uuid,
        annotation_sage_uuid,
        job_uuid,
        algorithm,
    ):
        from app.extensions.acm import default_acm_individual_uuid

        (
            matching_set_individual_uuids,
            matching_set_annot_uuids,
        ) = self.get_matching_set_data(annotation_uuid, matching_set_config)

        assert len(matching_set_individual_uuids) == len(matching_set_annot_uuids)

        # Sage doesn't support an empty database set, so if no annotations, don't send the request
        if len(matching_set_individual_uuids) == 0:
            return {}

        from app.extensions.acm import to_acm_uuid
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
            raise HoustonException(log, f'failed to find {algorithm}')

        id_request = {
            'jobid': str(job_uuid),
            'callback_url': f'houston+{callback_url}',
            'callback_detailed': True,
            'matching_state_list': [],
            'query_annot_name_list': [default_acm_individual_uuid()],
            'query_annot_uuid_list': [
                to_acm_uuid(annotation_sage_uuid),
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
        from app.extensions.acm import encode_acm_request

        if not self.id_configs:
            log.warning('send_identification called without id_configs')
            self.stage = SightingStage.failed
            return

        log.debug(
            f'In send_identification for cnf:{config_id}  algo:{algorithm_id} '
            f'Ann UUID:{annotation_uuid}  Ann content_guid:{annotation_sage_uuid}'
        )

        # Message construction has to be in the task as the jobId must be unique
        job_uuid = uuid.uuid4()
        matching_set_config = self.id_configs[config_id].get('matching_set')
        algorithm = self.id_configs[config_id]['algorithms'][algorithm_id]
        if not annotation_sage_uuid:
            log.warning(
                f'Sage Identification on Sighting({self.guid}) Job({job_uuid}) '
                f'aborted due to no content_guid on Annotation {annotation_uuid}'
            )
            self.stage = SightingStage.failed
            return
        id_request = self.build_identification_request(
            matching_set_config,
            annotation_uuid,
            annotation_sage_uuid,
            job_uuid,
            algorithm,
        )
        if id_request != {}:
            encoded_request = encode_acm_request(id_request)
            try:
                current_app.acm.request_passthrough_result(
                    'job.identification_request', 'post', {'params': encoded_request}
                )

                log.info(f'Sent ID Request, creating job {job_uuid}')
                self.jobs[str(job_uuid)] = {
                    'matching_set': matching_set_config,
                    'algorithm': algorithm,
                    'annotation': str(annotation_uuid),
                    'annotation_sage_uuid': str(annotation_sage_uuid),
                    'active': True,
                    'start': datetime.utcnow(),
                }
                # This is necessary because we can only mark self as modified if
                # we assign to one of the database attributes
                self.jobs = self.jobs
                with db.session.begin(subtransactions=True):
                    db.session.merge(self)
            except HoustonException as ex:
                acm_status_code = ex.get_val('acm_status_code', None)
                if (
                    ex.status_code == HTTPStatus.SERVICE_UNAVAILABLE
                    or ex.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
                ):
                    if (
                        self._get_attempts_for_config(
                            config_id, algorithm_id, str(annotation_uuid)
                        )
                        < MAX_IDENTIFICATION_ATTEMPTS
                    ):
                        log.warning(
                            f'Sage Identification on Sighting({self.guid}) Job({job_uuid}) failed to start '
                            f'code: {ex.status_code}, acm_status_code: {acm_status_code}, retrying'
                        )
                        annotation = Annotation.find(annotation_uuid)
                        assert annotation
                        self.send_annot_for_detection(annotation, config_id, algorithm_id)
                    else:
                        log.warning(
                            f'Sage Identification on Sighting({self.guid}) Job({job_uuid}) failed to start '
                            f'code: {ex.status_code}, acm_status_code: {acm_status_code}, giving up'
                        )
                        self.stage = SightingStage.failed

        else:
            # TODO, this is correct for MVP as there is only one id per Sighting but this will need
            # rework when there are multiple
            self.stage = SightingStage.un_reviewed

    # validate that the id response is a valid format and extract the data required from it
    def _parse_id_response(self, job_id_str, data):
        from app.extensions.acm import from_acm_uuid

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
                'image_url': annot.asset.get_image_url(),
                'asset_dimensions': annot.asset.get_dimensions(),
                'bounds': annot.bounds,
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
            if not q_annot_job['result']:
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
            if self.jobs:
                size_range = (
                    stage_base_sizes[SightingStage.identification]
                    - stage_base_sizes[self.stage]
                )
                complete_jobs = [job for job in self.jobs.values() if not job['active']]
                completion += size_range * (len(complete_jobs) / len(self.jobs))
        return completion

    def set_asset_group_sighting(self, ags):
        self.asset_group_sighting = ags
        self.id_configs = ags.get_id_configs()
        if not self.id_configs:
            # If no configs passed by the user, use the first one from the IA Config
            from app.modules.ia_config_reader import IaConfig

            ia_config_reader = IaConfig(current_app.config.get('CONFIG_MODEL'))

            identifiers = ia_config_reader.get('_identifiers')
            self.id_configs = [{'algorithms': [list(identifiers.keys())[0]]}]

    def ia_pipeline(self):
        assert self.stage == SightingStage.identification

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

    def ia_pipeline(self):
        from .tasks import send_identification

        assert self.stage == SightingStage.identification
        self.validate_id_configs()
        encounters_with_annotations = [
            encounter for encounter in self.encounters if len(encounter.annotations) != 0
        ]

        num_jobs = 0
        if encounters_with_annotations:
            # Use task to send ID req with retries
            # Once we support multiple IA configs and algorithms, the number of jobs is going to grow....rapidly
            for config_id in range(len(self.id_configs)):
                for algorithm_id in range(len(self.id_configs[config_id]['algorithms'])):
                    for encounter in encounters_with_annotations:
                        for annotation in encounter.annotations:
                            if self.send_annot_for_detection(
                                annotation, config_id, algorithm_id
                            ):
                                log.warning(
                                    f'Skipping {annotation} due to lack of content_guid or encounter'
                                )
                                continue
                            # force this to be up-to-date in index, just to be safe
                            if config_id == 0:
                                annotation.index()
                            # load=False should get us this response quickly, cuz we just want a count
                            matching_set = annotation.get_matching_set(
                                self.id_configs[config_id].get('matching_set'), load=False
                            )
                            if not matching_set:
                                log.info(
                                    f'Skipping {annotation} due to empty matching set'
                                )
                                continue
                            log.debug(
                                f'[{num_jobs}] queueing up ID job for config_id={config_id} {annotation}: matching_set size={len(matching_set)} algo {algorithm_id}'
                            )
                            send_identification.delay(
                                str(self.guid),
                                config_id,
                                algorithm_id,
                                annotation.guid,
                                annotation.content_guid,
                            )
                            num_jobs += 1

        if num_jobs > 0:
            log.info(
                f'Started Identification for Sighting:{self.guid} using {num_jobs} jobs'
            )

        else:
            self.stage = SightingStage.un_reviewed
            log.info(
                f'Sighting {self.guid} un-reviewed, identification not needed or not possible (jobs=0); '
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

    def send_annot_for_detection(
        self, annotation, config_id, algorithm_id, restart=False
    ):
        from .tasks import send_identification

        log.debug(
            f'Processing ID for Sighting:{self.guid}, config:{config_id}, algo:{algorithm_id} '
            f'annot:{annotation.guid}, sage_annot:{annotation.content_guid} enc:{annotation.encounter_guid}'
        )
        if not annotation.content_guid or not annotation.encounter_guid:
            log.warning(f'Skipping {annotation} due to lack of content_guid or encounter')
            return False
        # force this to be up-to-date in index, just to be safe
        annotation.index()

        # load=False should get us this response quickly, cuz we just want a count
        matching_set = annotation.get_matching_set(
            self.id_configs[config_id].get('matching_set'), load=False
        )
        if not matching_set:
            log.info(f'Skipping {annotation.guid} due to empty matching set')
            return False

        if self._has_active_jobs(algorithm_id, str(annotation.guid)):
            log.info(
                f'Skipping {annotation.guid} as already an active job for {algorithm_id}'
            )
            return False

        log.debug(
            f'Queueing up ID job for config_id={config_id} {annotation}: '
            f'matching_set size={len(matching_set)} algo {algorithm_id}'
        )
        send_identification.delay(
            str(self.guid),
            config_id,
            algorithm_id,
            annotation.guid,
            annotation.content_guid,
        )

        # store that we sent it (handles retry counts)
        self._update_job_config(config_id, algorithm_id, str(annotation.guid), restart)
        return True

    def _get_job_config(self, config_id, algorithm_id, annotation_guid_str):
        for job_cnf in self.job_configs:
            # { 'configId': config, 'algorithmId': algorithm, 'annotation': str(annotation_uuid), 'num_tries': 1 }
            if (
                job_cnf['configId'] == config_id
                and job_cnf['algorithmId'] == algorithm_id
                and job_cnf['annotation'] == annotation_guid_str
            ):
                return job_cnf
            return {}

    def _update_job_config(self, config_id, algorithm_id, annotation_guid_str, restart):
        job_cnf = self._get_job_config(config_id, algorithm_id, annotation_guid_str)
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

    def _get_attempts_for_config(self, config_id, algorithm_id, annotation_guid_str):
        job_cnf = self._get_job_config(config_id, algorithm_id, annotation_guid_str)
        if job_cnf:
            return job_cnf['num_tries']
        else:
            return 0

    def _has_active_jobs(self, algorithm_id, annotation_guid_str):
        for job in self.jobs:
            if (
                self.jobs[job]['algorithm'] == algorithm_id
                and self.jobs[job]['annotation'] == annotation_guid_str
            ):
                return self.jobs[job]['active']
        return False
