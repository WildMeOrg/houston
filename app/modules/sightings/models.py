# -*- coding: utf-8 -*-
"""
Sightings database models
--------------------
"""

from app.extensions import FeatherModel, HoustonModel, db
import uuid
import logging
import enum
from flask import current_app

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SightingAssets(db.Model, HoustonModel):
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

    # A sighting may have multiple IaConfigs used for IA on Sage, each with multiple algorithms,
    # even if only one is supported for MVP, Store as Json obj List
    # Content = ['matching_set': 'mine'|'extended'|'all', algorithms:[algo_1, algo_2]]
    ia_configs = db.Column(db.JSON, default={}, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
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
                    )
                    details[job_id][
                        'response'
                    ] = current_app.acm.request_passthrough_result(
                        'job.response', 'post', {}, job_id
                    )

        return details

    def delete(self):
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
        edm_json['createdHouston'] = self.created.isoformat()
        edm_json['updatedHouston'] = self.updated.isoformat()
        if (self.encounters is not None and edm_json['encounters'] is None) or (
            self.encounters is None and edm_json['encounters'] is not None
        ):
            log.warning('Only one None encounters value between edm/feather objects!')
        if self.encounters is not None and edm_json['encounters'] is not None:
            if len(self.encounters) != len(edm_json['encounters']):
                log.warning('Imbalanced encounters between edm/feather objects!')
                raise ValueError('imbalanced encounter count between edm/feather')
            else:
                i = 0
                while i < len(self.encounters):  # now we augment each encounter
                    found_edm = None
                    for edm_enc in edm_json['encounters']:
                        if edm_enc['id'] == str(self.encounters[i].guid):
                            found_edm = edm_enc
                    if found_edm is None:
                        raise ValueError(
                            f'could not find edm encounter matching {self.encounters[i]}'
                        )
                    self.encounters[i].augment_edm_json(found_edm)
                    i += 1
        if self.sighting_assets is None or len(self.sighting_assets) < 1:
            return edm_json
        from app.modules.assets.schemas import DetailedAssetSchema

        asset_schema = DetailedAssetSchema(
            many=False, only=('guid', 'filename', 'src', 'annotations')
        )
        edm_json['assets'] = []
        for asset in self.get_assets():
            json, err = asset_schema.dump(asset)
            edm_json['assets'].append(json)
        edm_json['featuredAssetGuid'] = self.get_featured_asset_guid()

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
        from app.modules.encounters.models import Encounter

        for enc_id in edm_map.keys():
            log.debug(f'adding new houston Encounter guid={enc_id}')
            user_guid = user.guid if user else None
            encounter = Encounter(
                guid=enc_id,
                version=edm_map[enc_id].get('version', 3),
                owner_guid=user_guid,
                submitter_guid=user_guid,
            )
            self.add_encounter(encounter)

    def get_matching_set_data(self, matching_set_data):
        annots = []
        from app.extensions.acm import to_acm_uuid

        # Must match the options validated in the metadata.py
        if matching_set_data == 'mine':
            data_owner = self.single_encounter_owner()
            assert data_owner
            annots = data_owner.get_my_annotations()
        elif matching_set_data == 'extended':
            data_owner = self.single_encounter_owner()
            assert data_owner
            annots = data_owner.get_all_annotations()
        elif matching_set_data == 'all':
            from app.modules.annotations.models import Annotation

            annots = Annotation.query.all()
        else:
            # Should have been caught at the metadata validation
            log.error(f'MatchingDataSet {matching_set_data} not supported')

        unique_annots = set(annots)
        matching_set_individual_uuids = []
        matching_set_annot_uuids = []
        for annot in unique_annots:
            if annot.encounter.sighting.stage == SightingStage.processed:
                matching_set_individual_uuids.append(annot.get_name())
                matching_set_annot_uuids.append(to_acm_uuid(annot.guid))

        return matching_set_individual_uuids, matching_set_annot_uuids

    def build_identification_request(self, config_id, annotation_uuid, job_uuid):
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
        callback_url = f'{base_url}api/v1/asset_group/sighting/{str(self.guid)}/sage_identified/{str(job_uuid)}'
        # TODO Needs more work, model info not even started, Sage is rejecting this
        id_request = {
            'jobid': str(job_uuid),
            'callback_url': callback_url,
            'matching_state_list': [],
            'query_annot_name_list': ['____'],
            'query_annot_uuid_list': [
                to_acm_uuid(annotation_uuid),
            ],
            'query_config_dict': {'sv_on': True},
            'database_annot_name_list': matching_set_individual_uuids,
            'database_annot_uuid_list': matching_set_annot_uuids,
        }
        return id_request

    def send_identification(self, config_id, algorithm_id, annotation_uuid):
        from datetime import datetime

        # Message construction has to be in the task as the jobId must be unique
        job_uuid = uuid.uuid4()
        matching_set_data = self.ia_configs[config_id].get('matchingSetDataOwners')
        algorithm = self.ia_configs[config_id]['algorithms'][algorithm_id]
        id_request = self.build_identification_request(
            matching_set_data, annotation_uuid, job_uuid
        )
        if id_request != {}:
            current_app.acm.request_passthrough_result(
                'job.identification_request', 'post', {'params': id_request}
            )

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
        else:
            self.stage = SightingStage.un_reviewed

    # Return the contents of the last ID request sent for the annotation Id, status and any response
    def get_last_identification_data(self, annotation_uuid):
        id_data = {}
        # TODO, DEX-354 iterate through self.jobs looking for annotation_uuid,
        # for the last one (calculated by looking at the start time)
        # Use the matching_set, algorithm and job_uuid from the job, to rebuild the request sent
        # using  build_identification_request
        # store this as id_data.request
        # store job active in id_data.active
        # request response for this job from Sage and store in id_data.response
        return id_data

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll ACM to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True

    def ia_pipeline(self, id_configs):
        from .tasks import send_identification

        assert self.stage == SightingStage.identification
        num_algorithms = 0

        self.ia_configs = id_configs
        num_configs = len(id_configs)
        if num_configs > 0:
            # Only one for MVP
            assert num_configs == 1
            for config in self.ia_configs:
                assert 'algorithms' in config
                # Only one for MVP
                assert len(config['algorithms']) == 1
                assert 'matchingSetDataOwners' in config
                num_algorithms += len(config['algorithms'])

                # For now, regions are ignored

        encounters_with_annotations = [
            encounter for encounter in self.encounters if len(encounter.annotations) != 0
        ]

        # No annotations to identify or no algorithms, go straight to un-reviewed
        if len(encounters_with_annotations) == 0 or num_algorithms == 0:
            self.stage = SightingStage.un_reviewed
        else:
            # Use task to send ID req with retries
            # Once we support multiple IA configs and algorithms, the number of jobs is going to grow....rapidly
            for config_id in range(len(self.ia_configs)):
                for algorithm_id in range(len(self.ia_configs[config_id]['algorithms'])):
                    for encounter in self.encounters:
                        for annotation in encounter.annotations:
                            send_identification(
                                self.guid,
                                config_id,
                                algorithm_id,
                                annotation.guid,
                            )
