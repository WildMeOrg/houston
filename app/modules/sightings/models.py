# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""
import datetime  # NOQA
import enum
import logging
import uuid
from http import HTTPStatus

from flask import current_app, url_for

import app.extensions.logging as AuditLog
from app.extensions import CustomFieldMixin, HoustonModel, db
from app.modules.annotations.models import Annotation
from app.modules.encounters.models import Encounter
from app.modules.individuals.models import Individual
from app.utils import HoustonException

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


class SightingTaxonomies(db.Model):
    sighting_guid = db.Column(db.GUID, db.ForeignKey('sighting.guid'), primary_key=True)
    taxonomy_guid = db.Column(db.GUID, primary_key=True)


class SightingStage(str, enum.Enum):
    identification = 'identification'
    un_reviewed = 'un_reviewed'
    processed = 'processed'
    failed = 'failed'


class Sighting(db.Model, HoustonModel, CustomFieldMixin):
    """
    Sightings database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

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

    decimal_latitude = db.Column(db.Float, nullable=True)
    decimal_longitude = db.Column(db.Float, nullable=True)

    # Matches guid in site.custom.regions
    # This is logically required on a sighting so should not really be nullable
    # but so much migrated data will not have it that it must be nullable for now
    location_guid = db.Column(db.GUID, index=True, nullable=True)

    taxonomy_joins = db.relationship('SightingTaxonomies')

    comments = db.Column(db.String(), nullable=True)
    verbatim_locality = db.Column(db.String(), nullable=True)

    custom_fields = db.Column(db.JSON, default=lambda: {}, nullable=True)

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

    @classmethod
    def patch_elasticsearch_mappings(cls, mappings):
        mappings = super(Sighting, cls).patch_elasticsearch_mappings(mappings)

        # this *adds* location_geo_point - but only at top-level
        if '_schema' in mappings:
            mappings['location_geo_point'] = {'type': 'geo_point'}

        if 'customFields' in mappings:
            mappings['customFields'] = cls.custom_field_elasticsearch_mappings(
                mappings['customFields']
            )

        if 'individualNames' in mappings:
            mappings['individualNames'] = {
                'type': 'keyword',
                'normalizer': 'codex_keyword_normalizer',
            }

        if 'individualNamesWithContexts' in mappings:
            for context in mappings['individualNamesWithContexts']['properties']:
                mappings['individualNamesWithContexts']['properties'][context] = {
                    'type': 'keyword',
                    'normalizer': 'codex_keyword_normalizer',
                }

        return mappings

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
            sighting.delete()

    def get_owners(self):
        owners = []
        for encounter in self.get_encounters():
            if encounter.get_owner() is not None and encounter.get_owner() not in owners:
                owners.append(encounter.get_owner())
        return owners

    def get_owner(self):
        # this is what we talked about but it makes me squeamish
        if self.get_owners():
            return self.get_owners()[0]
        return None

    def get_creator(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting.get_owner()
        else:
            return None

    def get_location_id(self):
        return self.location_guid

    def get_location_id_value(self):
        from app.modules.site_settings.models import Regions

        return Regions.get_region_name(str(self.location_guid))

    def get_location_id_keyword(self):
        from app.extensions.elasticsearch import MAX_UNICODE_CODE_POINT_CHAR

        location_id_value = self.get_location_id_value()
        if location_id_value is None:
            location_id_value = MAX_UNICODE_CODE_POINT_CHAR
        location_id_keyword = location_id_value.strip().lower()
        return location_id_keyword

    # primarly for elasticsearch; see: https://www.elastic.co/guide/en/elasticsearch/reference/current/geo-point.html
    def get_geo_point(self):
        if self.decimal_latitude is None or self.decimal_longitude is None:
            return None
        # we might consider validating these; but for now we trust the data (ha!)
        return {'lat': self.decimal_latitude, 'lon': self.decimal_longitude}

    def get_locality(self):
        return self.verbatim_locality

    def get_taxonomies(self):
        from app.modules.site_settings.models import Taxonomy

        tx_guids = [tx.taxonomy_guid for tx in self.taxonomy_joins]
        txs = []
        for tx_guid in tx_guids:
            try:
                txs.append(Taxonomy(tx_guid))
            except Exception:
                # An integrity check will be added to find (and potentially fix) these
                AuditLog.audit_log_object_warning(
                    log,
                    self,
                    f'found invalid taxonomy_guid {tx_guid} on sighting {self.guid}',
                )
        return txs

    def get_taxonomy_guids(self):
        # we use get_taxonomies() as it will validate taxonomy guid
        return [tx.guid for tx in self.get_taxonomies()]

    # this basically gives a superset of (unique) taxonomy guids
    def get_taxonomy_guids_with_encounters(self):
        txs = self.get_taxonomy_guids()
        for enc in self.encounters:
            if enc.taxonomy_guid and enc.taxonomy_guid not in txs:
                txs.append(enc.taxonomy_guid)
        return txs

    # Taxonomy objects, so we "can trust the guids"  :/
    def set_taxonomies(self, txs):
        with db.session.begin(subtransactions=True):
            for rel in self.taxonomy_joins:
                db.session.delete(rel)
            rels = self.taxonomy_joins or []
            for tx in txs:
                rel = SightingTaxonomies(sighting_guid=self.guid, taxonomy_guid=tx.guid)
                db.session.add(rel)
                rels.append(rel)
            self.taxonomy_joins = rels
            db.session.merge(self)

    def add_taxonomy(self, tx):
        rels = self.taxonomy_joins or []
        if tx in self.get_taxonomies():
            return
        with db.session.begin():
            rel = SightingTaxonomies(sighting_guid=self.guid, taxonomy_guid=tx.guid)
            db.session.add(rel)
            rels.append(rel)
            self.taxonomy_joins = rels
            db.session.merge(self)

    def get_custom_fields(self):
        return self.custom_fields

    def init_progress_identification(self, overwrite=False):
        from app.modules.progress.models import Progress

        if self.progress_identification:
            if overwrite:
                self.progress_identification.cancel()
            else:
                message = f'Sighting {self} already has a progress identification {self.progress_identification}'
                AuditLog.audit_log_object_warning(log, self, message)
                log.warning(message)
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

    def get_number_encounters(self):
        return len(self.encounters)

    def add_encounter(self, encounter):
        if encounter not in self.encounters:
            with db.session.begin(subtransactions=True):
                self.encounters.append(encounter)
                db.session.merge(self)

    def remove_encounter(self, encounter):
        if encounter in self.encounters:
            with db.session.begin(subtransactions=True):
                self.encounters.remove(encounter)
                db.session.merge(self)

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

    def get_number_assets(self):
        return len(self.get_all_assets())

    def get_annotations(self):
        annots = []
        for enc in self.encounters:
            if enc.annotations:
                annots += enc.annotations
        return annots

    def get_number_annotations(self):
        return len(self.get_annotations())

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

    # returns the furthest pipeline got that is not complete
    def get_pipeline_state(self):
        status = self.get_pipeline_status()
        for st in ['preparation', 'detection', 'curation', 'identification']:
            if not (
                status[st].get('complete', False) or status[st].get('skipped', False)
            ):
                return st
        return None

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

    # this piggybacks off of AssetGroupSighting.... *if* we have one!
    #   otherwise we assume we are migrated and kinda fake it
    def _get_pipeline_status_preparation(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting._get_pipeline_status_preparation()
        # migration means faking preparation complete
        status = {
            'skipped': False,
            'inProgress': False,
            'failed': False,
            'complete': True,
            'message': 'migrated data; fabricated status',
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
        return status

    # this piggybacks off of AssetGroupSighting.... *if* we have one!
    #   otherwise we assume we are migrated and kinda fake it
    def _get_pipeline_status_detection(self):
        if self.asset_group_sighting:
            return self.asset_group_sighting._get_pipeline_status_detection()

        # for migrated data we *assume* detection was run and completed
        #   we may want to revisit this later if this leads to weirdness
        status = {
            'skipped': False,
            'inProgress': False,
            'failed': False,
            'complete': True,
            'message': 'migrated data; fabricated status',
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
        return status

    def _get_pipeline_status_curation(self):
        if self.asset_group_sighting:
            status = self.asset_group_sighting._get_pipeline_status_curation()
            # the fact that we are in a sighting means curation is finished
            #    and this means it can only be skipped or complete
            #    so we "repair" the AGS-provided status if it says otherwise
            if not status['skipped'] and not status['complete']:
                status['complete'] = True
                status['skipped'] = False
                status['failed'] = False
                status['inProgress'] = False
                status['progress'] = 1
                status[
                    '_note'
                ] = 'repaired a questionable AssetGroupSighting curation status'
            # and we need something for these, so....
            if status['complete'] and not status['start']:
                status['start'] = (self.created.isoformat() + 'Z',)
            if status['complete'] and not status['end']:
                status['end'] = (self.created.isoformat() + 'Z',)

        else:
            status = {
                'skipped': False,
                'inProgress': False,
                'failed': False,
                'complete': True,
                'message': 'migrated data; fabricated status',
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

        # leaving this for prosperity and consideration, but going to comment out for now
        #
        # The curation stage starts when manual annotation OR detection adds the first annotation to the asset group sighting.
        # annotations = self.get_annotations()
        # if annotations and len(annotations) > 1:
        #    times = [ann.created for ann in annotations]
        #    first_time = min(times)
        #    status['start'] = first_time.isoformat() + 'Z'
        # else:
        #    status['start'] = self.created.isoformat() + 'Z'
        return status

    def _get_pipeline_status_identification(self):
        from app.modules.progress.models import ProgressStatus

        progress = self.progress_identification
        # no progress object, we assume it has not yet started
        if not progress:
            status = {
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
            # if migrated, should look skipped rather than not started
            if self.is_migrated_data():
                status['skipped'] = True
            return status

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

    def any_jobs_active(self):
        jobs = self.jobs
        if not jobs:
            return False
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job.get('active', False):
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
                annot = None
                annot_guid = self.jobs[job_id].get('annotation')
                if annot_guid:
                    from app.modules.annotations.models import Annotation

                    annot = Annotation.query.get(annot_guid)
                if not annot:
                    details[-1]['request'] = 'No annotation in job'
                else:
                    details[-1]['request'] = self.build_identification_request(
                        annot,
                        self.jobs[job_id].get('matching_set'),
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

    @property
    def individuals(self):
        indivs = set()
        for enc in self.encounters:
            if enc.individual_guid:
                indivs.add(enc.individual)
        return indivs

    def get_individual_names(self):
        names = set()
        for indiv in self.individuals:
            names.update(indiv.get_name_values())
        return names

    def get_individual_names_with_contexts(self):
        nwc = {}
        for indiv in self.individuals:
            for name in indiv.names:
                if name.context not in nwc:
                    nwc[name.context] = set()
                nwc[name.context].add(name.value_resolved)
        return nwc

    def delete(self):
        AuditLog.delete_object(log, self)
        with db.session.begin(subtransactions=True):
            while self.sighting_assets:
                db.session.delete(self.sighting_assets.pop())
            while self.encounters:
                self.encounters.pop().delete()
            while self.taxonomy_joins:
                db.session.delete(self.taxonomy_joins.pop())
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
            while self.taxonomy_joins:
                db.session.delete(self.taxonomy_joins.pop())
            db.session.delete(self)
            while assets:
                asset = assets.pop()
                asset.delete()

    def delete_frontend_request(self, delete_individual):
        response = {}

        individuals = [
            enc.individual
            for enc in self.encounters
            if enc.individual and len(enc.individual.encounters) == 1
        ]
        if not delete_individual and individuals:
            # EDM could only report the first vulnerable Individual it found so that is sadly the API
            # we are left with
            response['vulnerableIndividual'] = individuals[0].guid
            return False, response

        if individuals:
            response['deletedIndividuals'] = []
            for ind in individuals:
                response['deletedIndividuals'].append(str(ind.guid))
                ind.delete()

        self.delete()
        return True, response

    def get_detailed_json(self):
        from .schemas import DetailedSightingSchema

        sighting_schema = DetailedSightingSchema()
        return sighting_schema.dump(self).data

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
        checksum_set = []
        unique_set = set()  # just to prevent duplication
        for annot in matching_set_annotations:
            checksum_set.append(annot.guid)
            # ideally the query on matching_set annots will exclude these, but in case someone got fancy:
            if not annot.content_guid:
                message = f'skipping {annot} due to no content_guid'
                AuditLog.audit_log_object_warning(log, self, message)
                log.warning(message)
                continue

            # this *does* assume the sighting exists due to elasticsearch constraints, in order to improve performance.
            #   it previously was this, which took longer as it needed to load two objects from db:
            #          if annot.encounter and annot.encounter.sighting:

            if annot.content_guid not in unique_set:
                unique_set.add(annot.content_guid)

                individual_guid = annot.get_individual_guid()
                if individual_guid:
                    individual_guid = str(individual_guid)
                else:
                    # Use Sage default value
                    individual_guid = SAGE_UNKNOWN_NAME

                matching_set_annot_uuids.append(annot.content_guid)
                matching_set_individual_uuids.append(individual_guid)

        checksum_pre = annotation.matching_set_checksum(checksum_set)
        checksum_post = annotation.matching_set_checksum(matching_set_annot_uuids)
        # Ensure that the annotation we are querying on is in the database list as well
        matching_set_annot_uuids = list(
            map(to_sage_uuid, sorted(set(matching_set_annot_uuids)))
        )
        log.debug(
            f'sighting.get_matching_set_data() [annot {str(annotation.guid)}] checksums: {checksum_pre} / {checksum_post}'
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
        ia_config_reader = IaConfig()
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
            self.progress_identification.skip()
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

        # Ensure Sage is completely up-to-date
        if current_app.testing:
            Annotation.sync_all_with_sage(ensure=True)

        if annotation.progress_identification:
            annotation.progress_identification.set(2)

        if not self.id_configs:
            message = 'send_identification called without id_configs'
            AuditLog.audit_log_object_warning(log, self, message)
            log.warning(message)
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
                                message = f'{debug_context} Sage Identification failed to start '
                                message += f'code: {ex.status_code}, sage_status_code: {sage_status_code}, retrying'
                                AuditLog.audit_log_object_warning(log, self, message)
                                log.warning(message)

                                self.send_annotation_for_identification_specific(
                                    annotation, config_id, algorithm_id, restart=False
                                )
                            else:
                                message = f'{debug_context} Sage Identification failed to start '
                                message += f'code: {ex.status_code}, sage_status_code: {sage_status_code}, giving up'
                                AuditLog.audit_log_object_warning(log, self, message)
                                log.warning(message)

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

        if 'cm_dict' in json_result and str(sage_uuid) in json_result['cm_dict']:
            result['extern_ref'] = json_result['cm_dict'][str(sage_uuid)].get(
                'dannot_extern_reference'
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
            algorithm = self.jobs[job_id_str]['algorithm']
            annot_guid = self.jobs[job_id_str]['annotation']
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

                ia_config_reader = IaConfig()
                id_config_dict = ia_config_reader.get(f'_identifiers.{algorithm}')
                assert id_config_dict
                frontend_data = id_config_dict.get('frontend', '')
                if frontend_data:
                    description = frontend_data.get('description', '')
            except KeyError:
                message = f'{debug_context} failed to find {algorithm},'
                AuditLog.audit_log_object_warning(log, self, message)
                log.warning(message)

            if annotation.progress_identification:
                annotation.progress_identification.set(92)

            log.info(
                f"{debug_context} Received successful response '{description}' from Sage for {job_id_str}"
            )
            log.debug(f'{debug_context} ID response stored result: {result}')

            # All good, mark job as finished
            with db.session.begin(subtransactions=True):
                self.jobs[job_id_str]['active'] = False
                self.jobs[job_id_str]['success'] = status == 'completed'
                self.jobs[job_id_str]['result'] = result
                self.jobs[job_id_str]['end'] = datetime.datetime.utcnow()
                self.jobs = self.jobs
                db.session.merge(self)

            db.session.refresh(self)

            if not self.any_jobs_active():
                self.set_stage(SightingStage.un_reviewed, refresh=False)
                with db.session.begin(subtransactions=True):
                    self.unreviewed_start = datetime.datetime.utcnow()
                    db.session.merge(self)
                db.session.refresh(self)
                message = f'Sighting {self.guid} all jobs completed'
                AuditLog.audit_log_object(log, self, message)

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
            message = f'check_job_status called for invalid job {job_id}'
            AuditLog.audit_log_object_warning(log, self, message)
            log.warning(message)
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
        q_annot = Annotation.query.get(q_annot_job.get('annotation'))
        # If no annot, assume that annot has been deleted since the job was run and use None
        if t_annot:
            data = {
                'guid': t_annot_guid,
                'score': t_annot_result[t_annot_guid],
                'id_finish_time': str(q_annot_job['end']),
                'heatmap_src': Sighting._heatmap_src(
                    q_annot_job['result'].get('extern_ref'),
                    str(q_annot.content_guid),
                    str(t_annot.content_guid),
                ),
            }

        return t_annot, data

    @classmethod
    def _heatmap_src(cls, extern_ref, q_annot_content_uuid, d_annot_content_uuid):
        if not extern_ref:
            return None
        import os

        import requests

        # uri will not work when localhost, so we kinda gotta cache this anyway and let have a "real" houston url
        #   FIXME this should be smarter in the future
        uri = current_app.config['SAGE_URIS']['default']
        filename = (
            f'sage-heatmap-{extern_ref}-{q_annot_content_uuid}-{d_annot_content_uuid}.jpg'
        )
        filepath = os.path.join(
            current_app.config.get('FILEUPLOAD_BASE_PATH', '/tmp'),
            'sage-heatmaps',
            filename,
        )
        if not os.path.exists(filepath):  # not already cached
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            sage_src = f'{uri}/api/query/graph/match/thumb/?extern_reference={extern_ref}&query_annot_uuid={q_annot_content_uuid}&database_annot_uuid={d_annot_content_uuid}&version=heatmask'
            resp = requests.get(sage_src)
            if not resp.headers['content-type'].lower().startswith('image/'):
                log.error(
                    f'non-image on fetching {sage_src} to {filepath}; contents in {filepath}.err'
                )
                open(filepath + '.err', 'wb').write(resp.content)
                return
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as err:
                log.error(f'error {str(err)} on fetching {sage_src} to {filepath}')
                return
            open(filepath, 'wb').write(resp.content)
        return f'/api/v1/annotations/sage-heatmaps/src/{filename}'

    # Helper to ensure that the required annot and individual data is present
    def _ensure_annot_data_in_response(self, annot, response):
        # encounterless annotations are Bad (or likely leaked in from uncommitted ags)
        #   so we dont report them as results.  see DEX-1027
        if not annot.encounter:
            log.warning(f'id_result for {self} skipping encounterless {annot}')
            return

        # will populate individual_first_name in next block to save a database hit
        individual_guid = annot.encounter.individual_guid
        individual = Individual.query.get(individual_guid) if individual_guid else None

        if str(annot.guid) not in response['annotation_data'].keys():
            # add annot data
            image_url = url_for(
                'api.sightings_sighting_id_result_annotation_src_asset',
                sighting_guid=self.guid,
                annotation_guid=annot.guid,
                _external=True,
            )
            encounter = annot.encounter
            sighting = annot.get_sighting()
            response['annotation_data'][str(annot.guid)] = {
                'viewpoint': annot.viewpoint,
                'encounter_location': encounter.get_location_id(),
                'individual_guid': str(individual.guid) if individual else None,
                'image_url': image_url,
                'asset_dimensions': annot.asset.get_dimensions(),
                'bounds': annot.bounds,
                'sighting_guid': str(sighting.guid),
                'sighting_time': sighting.get_time_isoformat_in_timezone(),
                'sighting_time_specificity': sighting.get_time_specificity(),
                'encounter_guid': str(encounter.guid),
                'asset_filename': annot.asset.filename,
                'individual_first_name': individual.get_first_name()
                if individual
                else None,
            }

        if (
            individual is not None
            and str(individual.guid) not in response['individual_data'].keys()
        ):
            # add individual data
            response['individual_data'][str(individual.guid)] = {
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
            if q_annot_job.get('active', False):
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

    def get_matched_annotation_guids(self):
        res = self.get_id_result()
        if not res or 'annotation_data' not in res:
            return []
        return [uuid.UUID(q) for q in res['annotation_data']]

    def set_asset_group_sighting(self, ags):
        self.asset_group_sighting = ags
        self.id_configs = ags.get_id_configs()

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

    def ia_pipeline(self, foreground=None, progress_overwrite=False):
        # For reasons that are not really clear, migrated sightings have jobs = None.
        # This causes all sorts of problems on ID so set it to a sane value
        if not self.jobs:
            with db.session.begin(subtransactions=True):
                self.jobs = {}
                db.session.merge(self)

        self.init_progress_identification(overwrite=progress_overwrite)

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
            message = f'{debug_context} Skipping {annotation} due to lack of content_guid or encounter'
            AuditLog.audit_log_object_warning(log, self, message)
            log.warning(message)

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
                return self.jobs[job].get('active', False)
        return False

    def _get_algorithm_name(self, config_id, algorithm_id):
        return self.id_configs[config_id]['algorithms'][algorithm_id]
