# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

import logging
import uuid

from flask import current_app

import app.extensions.logging as AuditLog
from app.extensions import HoustonModel, SageModel, db
from app.modules import is_module_enabled
from app.utils import HoustonException

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AnnotationKeywords(db.Model, HoustonModel):
    annotation_guid = db.Column(
        db.GUID, db.ForeignKey('annotation.guid'), primary_key=True
    )
    keyword_guid = db.Column(
        db.GUID, db.ForeignKey('keyword.guid', ondelete='CASCADE'), primary_key=True
    )
    annotation = db.relationship('Annotation', back_populates='keyword_refs')
    keyword = db.relationship('Keyword')


class Annotation(db.Model, HoustonModel, SageModel):
    """
    Annotations database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)
    content_guid = db.Column(db.GUID, nullable=True)

    asset_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset.guid', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    asset = db.relationship('Asset', back_populates='annotations')

    if is_module_enabled('encounters'):
        encounter_guid = db.Column(
            db.GUID,
            db.ForeignKey('encounter.guid', ondelete='CASCADE'),
            index=True,
            nullable=True,
        )
        encounter = db.relationship(
            'Encounter',
            backref=db.backref(
                'annotations',
                primaryjoin='Encounter.guid == Annotation.encounter_guid',
                order_by='Annotation.guid',
            ),
        )
    else:
        encounter_guid = None

    keyword_refs = db.relationship('AnnotationKeywords')
    ia_class = db.Column(db.String(length=255), nullable=False)
    viewpoint = db.Column(db.String(length=255), nullable=False)
    bounds = db.Column(db.JSON, nullable=False)

    contributor_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    contributor = db.relationship(
        'User',
        backref=db.backref(
            'contributed_annotations',
            primaryjoin='User.guid == Annotation.contributor_guid',
            order_by='Annotation.guid',
        ),
        foreign_keys=[contributor_guid],
    )

    progress_identification_guid = db.Column(
        db.GUID, db.ForeignKey('progress.guid'), index=False, nullable=True
    )

    progress_identification = db.relationship(
        'Progress',
        foreign_keys='Annotation.progress_identification_guid',
    )

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def __init__(self, *args, **kwargs):
        if 'bounds' not in kwargs:
            raise ValueError('bounds are mandatory')
        if 'rect' not in kwargs['bounds']:
            raise ValueError('rect in bounds is mandatory')
        if 'theta' not in kwargs['bounds']:
            kwargs['bounds']['theta'] = 0
        super().__init__(*args, **kwargs)

    @classmethod
    def run_integrity(cls):
        from app.modules.asset_groups.models import AssetGroup

        result = {'no_content_guid': [], 'no_encounter': []}

        # Annots must always have a content guid
        no_contents = Annotation.query.filter(Annotation.content_guid.is_(None)).all()
        if no_contents:
            result['no_content_guid'] = [annot.guid for annot in no_contents]

        no_encounters = []
        if is_module_enabled('encounters'):
            no_encounters = Annotation.query.filter(
                Annotation.encounter_guid.is_(None)
            ).all()

        # just because an annot has no encounters does not immediately make this an integrity check failure
        # Annots in Assets in Asset groups that are not fully processed may validly not have an encounter
        for annot in no_encounters:
            assert annot.asset.git_store
            # Integrity only currently implemented on codex, not MWS
            assert isinstance(annot.asset.git_store, AssetGroup)

            if annot.asset.git_store.is_processed():
                result['no_encounter'].append(annot.guid)

        return result

    @classmethod
    def get_jobs_for_annotation(cls, annotation_guid, verbose):
        annot = Annotation.query.get(annotation_guid)
        if not annot:
            raise HoustonException(log, f'Annotation {annotation_guid} not found')

        return annot.get_job_debug(verbose)

    def get_job_debug(self, verbose):
        if self.encounter:
            return self.encounter.sighting.get_job_debug(self.guid, verbose)
        else:
            raise HoustonException(
                log, f'Annotation {self.guid} not connected to an encounter', obj=self
            )

    @classmethod
    def get_sage_sync_tags(cls):
        return 'annotation', 'annot'

    def sync_with_sage(
        self, ensure=False, force=False, bulk_sage_uuids=None, skip_asset=False, **kwargs
    ):
        from app.extensions.sage import SAGE_UNKNOWN_NAME, from_sage_uuid, to_sage_uuid

        if self.asset is None:
            message = f'Annotation {self} has no asset, cannot send annotation to Sage'
            AuditLog.audit_log_object_error(log, self, message)
            log.error(message)

            return

        if self.asset.mime_type not in current_app.config.get(
            'SAGE_MIME_TYPE_WHITELIST_EXTENSIONS', []
        ):
            log.info(
                'Cannot sync Annotation %r with unsupported SAGE MIME type %r on Asset, skipping'
                % (
                    self,
                    self.asset.mime_type,
                )
            )
            return

        # First, ensure that the annotation's asset has been synced with Sage
        if not skip_asset:
            self.asset.sync_with_sage(
                ensure=ensure, force=force, bulk_sage_uuids=bulk_sage_uuids, **kwargs
            )

        if self.asset.content_guid is None:
            message = f'Asset for Annotation {self} failed to send, cannot send annotation to Sage'
            AuditLog.audit_log_object_error(log, self, message)
            log.error(message)

            # We tried to sync the asset's content GUID, but that failed... it is likely that the asset's file is missing
            return

        if force:
            with db.session.begin(subtransactions=True):
                self.content_guid = None
                db.session.merge(self)
            db.session.refresh(self)

        if ensure:
            if self.content_guid is not None:
                if bulk_sage_uuids is not None:
                    # Existence checks can be slow one-by-one, bulk checks are better
                    if self.content_guid in bulk_sage_uuids.get('annotation', {}):
                        # We have found this Annotation on Sage, simply return
                        return
                else:
                    content_guid_str = str(self.content_guid)
                    sage_rowids = current_app.sage.request_passthrough_result(
                        'annotation.exists', 'get', args=content_guid_str, target='sync'
                    )
                    if len(sage_rowids) == 1 and sage_rowids[0] is not None:
                        # We have found this Asset on Sage, simply return
                        return

                # If we have arrived here, it means we have a non-NULL content guid that isn't on the Sage instance
                # Null out the local content GUID and restart
                with db.session.begin(subtransactions=True):
                    self.content_guid = None
                    db.session.merge(self)
                db.session.refresh(self)

        if self.content_guid is not None:
            return

        assert self.content_guid is None

        if self.encounter and self.encounter.individual:
            annot_name = str(self.encounter.individual.guid)
        else:
            annot_name = SAGE_UNKNOWN_NAME

        try:
            self.validate_bounds(self.bounds)
        except Exception:
            message = f'Annotation {self} failed to pass validate_bounds(), cannot send annotation to Sage'
            AuditLog.audit_log_object_error(log, self, message)
            log.error(message)

            return

        sage_request = {
            'image_uuid_list': [to_sage_uuid(self.asset.content_guid)],
            'annot_species_list': [self.ia_class],
            'annot_bbox_list': [self.bounds['rect']],
            'annot_name_list': [annot_name],
            'annot_theta_list': [self.bounds.get('theta', 0)],
        }
        sage_response = current_app.sage.request_passthrough_result(
            'annotation.create', 'post', {'json': sage_request}, target='sync'
        )
        sage_guid = from_sage_uuid(sage_response[0])

        with db.session.begin(subtransactions=True):
            self.content_guid = sage_guid
            db.session.merge(self)
        db.session.refresh(self)

    def init_progress_identification(self, parent=None, overwrite=False):
        from app.modules.progress.models import Progress

        if self.progress_identification:
            if overwrite:
                self.progress_identification.cancel()
            else:
                message = f'Annotation {self} already has a progress identification {self.progress_identification}'
                AuditLog.audit_log_object_warning(log, self, message)
                log.warning(message)
                return

        progress = Progress(
            description='Sage identification for Annotation {!r}'.format(self.guid)
        )
        with db.session.begin():
            db.session.add(progress)

        with db.session.begin():
            self.progress_identification_guid = progress.guid
            db.session.merge(self)

        db.session.refresh(self)

        # Assign the parent's progress
        if parent and self.progress_identification:
            with db.session.begin():
                self.progress_identification.parent_guid = parent.guid
            db.session.merge(self.progress_identification)

        db.session.refresh(self)

    # Assumes that the caller actually wants the debug data for the context of where the annotation came from.
    # Therefore, returns an amalgamation of the detailed Annot plus one of :
    # the sighting schema (if the annot has a sighting)
    # or the AGS if the annot is curated to be part of an AGS (user has done curation but not hit commit)
    # or the possible AGSs if the annot is not curated to be part of any AGS.
    def get_debug_json(self):
        from app.modules.asset_groups.schemas import DebugAssetGroupSightingSchema
        from app.modules.sightings.schemas import DebugSightingSchema

        from .schemas import DetailedAnnotationSchema

        ags_schema = DebugAssetGroupSightingSchema()
        annot_schema = DetailedAnnotationSchema()
        sighting_schema = DebugSightingSchema()

        returned_json = {'annotation': annot_schema.dump(self).data}

        if self.encounter:
            returned_json['sighting'] = sighting_schema.dump(self.encounter.sighting).data
            return returned_json

        assert self.asset.git_store
        ags = self.asset.git_store.get_asset_group_sighting_for_annotation(self)
        if ags:
            returned_json['asset_group_sighting'] = ags_schema.dump(ags).data
        else:
            # Annotation created but not curated into an AGS, instead use one the AGS of the asset
            ags_s = self.asset.git_store.get_asset_group_sightings_for_asset(self.asset)
            if len(ags_s) > 0:
                returned_json['possible_asset_group_sightings'] = []
                for ags_id in range(len(ags_s)):
                    returned_json['possible_asset_group_sightings'].append(
                        ags_schema.dump(ags_s[ags_id]).data
                    )

        return returned_json

    @property
    def keywords(self):
        return self.get_keywords()

    def get_keywords(self):
        return sorted(ref.keyword for ref in self.keyword_refs)

    def add_keyword(self, keyword):
        with db.session.begin(subtransactions=True):
            self.add_keyword_in_context(keyword)

    def add_keywords(self, keyword_list):
        with db.session.begin():
            for keyword in keyword_list:
                self.add_keyword_in_context(keyword)

    def add_keyword_in_context(self, keyword):
        for ref in self.keyword_refs:
            if ref.keyword == keyword:
                # We found the keyword in the annotation's existing refs, no further action needed
                return

        # If not, create the new annotation-keyword relationship
        rel = AnnotationKeywords(annotation=self, keyword=keyword)
        db.session.add(rel)
        self.keyword_refs.append(rel)

    def remove_keyword(self, keyword):
        with db.session.begin(subtransactions=True):
            self.remove_keyword_in_context(keyword)

    def remove_keyword_in_context(self, keyword):
        for ref in self.keyword_refs:
            if ref.keyword == keyword:
                db.session.delete(ref)
                break

    def user_is_owner(self, user):
        # Annotation has no owner, but it has one asset, that has one git store that has an owner
        # (encounter is no longer required on Annotation, so best route to owner is via Asset/Group)
        return self.asset.user_is_owner(user)

    # Used for building matching set but abstract the annotation to name mapping
    def get_individual_guid(self):
        # i think this technically might save a db hit vs get_individual() if only guid is needed
        return self.encounter.individual_guid if self.encounter else None

    def get_individual(self):
        individual = None
        if self.encounter and self.encounter.individual:
            individual = self.encounter.individual
        return individual

    def get_sighting(self):
        sighting = None
        if self.encounter:
            sighting = self.encounter.sighting

        return sighting

    def get_asset_src(self):
        assset_src = None
        if self.asset and self.asset.src:
            assset_src = self.asset.src
        return assset_src

    def get_matching_set(self, query=None, load=True):
        if not self.encounter_guid:
            raise ValueError(f'{self} has no Encounter so cannot be matched against')
        if not query or not isinstance(query, dict):
            query = self.get_matching_set_default_query()
        else:
            query = self.resolve_matching_set_query(query)
        matching_set = self.elasticsearch(query, load=load, limit=None)
        log.info(
            f'annot.get_matching_set(): finding matching set for {self} using (resolved) query {query} => {len(matching_set)} annots'
        )
        log.info(
            f'annot.get_matching_set() [annot {str(self.guid)}] checksum: {self.matching_set_checksum(matching_set)}'
        )
        return matching_set

    # this is really just a debugging thing that is a "thumbprint" of a matchingset
    def matching_set_checksum(self, matching_set):
        import hashlib

        guids = [
            str(a.guid) if isinstance(a, Annotation) else str(a) for a in matching_set
        ]
        guids.sort()
        return (
            f"{len(matching_set)}:{hashlib.sha256(''.join(guids).encode()).hexdigest()}"
        )

    def get_matching_set_default_query(self):
        # n.b. default will not take any locationId or ownership into consideration
        top_bool = {
            'must': {'bool': {}},  # required for all cases
            'should': [],  # OR'ed for: in AssetGroup (no enc/sight) || has enc/sight
            'minimum_should_match': 1,
        }

        viewpoint_list = self.get_neighboring_viewpoints()
        # TODO should we allow nulls?
        if viewpoint_list:
            viewpoint_data = []
            for vp in viewpoint_list:
                viewpoint_data.append({'term': {'viewpoint': vp}})
            top_bool['must']['bool']['minimum_should_match'] = 1
            top_bool['must']['bool']['should'] = viewpoint_data

        # for the AssetGroup (doesnt have encounter/sighting data)
        top_bool['should'].append(
            {'term': {'git_store_guid': self.get_git_store_guid_str()}}
        )

        # the second part of the OR for when we do have encounter/sighting data
        bool_es = {'filter': []}
        # same, re: nulls
        tx_guid = self.get_taxonomy_guid_str()
        if tx_guid:
            bool_es['filter'].append({'match': {'taxonomy_guid': tx_guid}})

        # requiring an encounter is equivalent to requiring a sighting, which seems reasonable (see DEX-1027)
        bool_es['filter'].append({'exists': {'field': 'encounter_guid'}})

        # removing this should keep matching-sets uniform for, say, regions
        #
        # if self.encounter_guid:
        #     bool_es['must_not'] = {'match': {'encounter_guid': str(self.encounter_guid)}}
        top_bool['should'].append({'bool': bool_es})

        return {'bool': top_bool}

    # this is to allow for manipulation of a user-provided query prior to actually using it
    #  e.g. we might want to _force_ criteria or remove certain filters, etc.
    def resolve_matching_set_query(self, query):
        if not query or not isinstance(query, dict):
            raise ValueError('must be passed a dict ES query')
        if not self.encounter_guid:
            raise ValueError('cannot resolve query on Annotation with no Encounter')
        # DEX-1147 leaves the critical criteria to the FE/caller to remember
        macroed = self.matching_set_query_replace_macros(query)
        return macroed

    # currently macros can only be *values*, not *keys*
    def matching_set_query_replace_macros(self, query):
        assert query and isinstance(query, dict)
        from copy import deepcopy

        replaced = deepcopy(query)
        for key in replaced:
            if isinstance(replaced[key], dict):  # recurse!
                replaced[key] = self.matching_set_query_replace_macros(replaced[key])
            elif isinstance(replaced[key], list):  # recurse!
                for i in range(len(replaced[key])):
                    if isinstance(replaced[key][i], dict) or isinstance(
                        replaced[key][i], list
                    ):
                        replaced[key][i] = self.matching_set_query_replace_macros(
                            replaced[key][i]
                        )
            elif isinstance(replaced[key], str) and replaced[key].startswith('_MACRO_'):
                macro_name = replaced[key][7:]
                if macro_name == 'annotation_neighboring_viewpoints_clause':
                    viewpoint_list = self.get_neighboring_viewpoints()
                    if not viewpoint_list:
                        replaced[key] = {}
                    else:
                        viewpoint_data = []
                        for vp in viewpoint_list:
                            viewpoint_data.append({'term': {'viewpoint': vp}})
                        replaced[key] = {
                            'minimum_should_match': 1,
                            'should': viewpoint_data,
                        }
                elif macro_name == 'annotation_git_store_guid':
                    replaced[key] = self.get_git_store_guid_str()
                elif macro_name == 'annotation_sighting_guid':
                    replaced[key] = self.get_sighting_guid_str()
                elif macro_name == 'annotation_encounter_guid':
                    replaced[key] = self.get_encounter_guid_str()
        return replaced

    # first tries encounter fields, but will use field on sighting if none on encounter,
    #   unless sighting_fallback=False
    def get_location_id(self, sighting_fallback=True):
        return (
            self.encounter.get_location_id(sighting_fallback)
            if self.encounter_guid
            else None
        )

    def get_location_id_str(self, sighting_fallback=True):
        guid = self.get_location_id(sighting_fallback)
        return str(guid) if guid else None

    def get_taxonomy_guid(self, sighting_fallback=True):
        return (
            self.encounter.get_taxonomy_guid(sighting_fallback)
            if self.encounter_guid
            else None
        )

    def get_taxonomy_guid_str(self, sighting_fallback=True):
        guid = self.get_taxonomy_guid(sighting_fallback)
        return str(guid) if guid else None

    def get_time_isoformat_in_timezone(self, sighting_fallback=True):
        return self.encounter and self.encounter.get_time_isoformat_in_timezone(
            sighting_fallback
        )

    def get_owner_guid_str(self):
        if not self.encounter_guid or not self.encounter:
            return None
        return self.encounter.get_owner_guid_str()

    def get_encounter_guid_str(self):
        return str(self.encounter_guid) if self.encounter_guid else None

    def get_sighting_guid_str(self):
        if not self.encounter_guid or not self.encounter:
            return None
        return self.encounter.get_sighting_guid_str()

    def get_git_store_guid_str(self):
        return str(self.asset.git_store.guid)

    def get_keyword_values(self):
        if not self.keyword_refs:
            return []
        return sorted(ref.keyword.value for ref in self.keyword_refs)

    def delete(self):
        # first we remove annot from any AGS it might be in (issue houston#906)
        for ags in self.asset.git_store.asset_group_sightings:
            ags.remove_annotation(str(self.guid))
            ags.config = ags.config
            with db.session.begin(subtransactions=True):
                db.session.merge(ags)
        with db.session.begin(subtransactions=True):
            while self.keyword_refs:
                ref = self.keyword_refs.pop()
                # this is actually removing the AnnotationKeywords refs (not actual Keywords)
                db.session.delete(ref)
                ref.keyword.delete_if_unreferenced()  # but this *may* remove keyword itself
            db.session.delete(self)

    def set_bounds(self, bounds):
        self.validate_bounds(bounds)
        self.bounds = bounds

    @classmethod
    def validate_bounds(cls, bounds):
        assert isinstance(bounds, dict)
        assert 'rect' in bounds
        assert isinstance(bounds['rect'], list)
        assert len(bounds['rect']) == 4

    @classmethod
    def create_bounds(cls, input_data):
        xtl = input_data.get('xtl')
        ytl = input_data.get('ytl')
        width = input_data.get('width')
        height = input_data.get('height')
        theta = input_data.get('theta', 0)

        if xtl is None or ytl is None or width is None or height is None:
            raise HoustonException(
                log,
                log_message=f'{input_data} missing fields',
                message='input Data needs xtl, ytl, width and height',
            )
        resp = {'rect': [xtl, ytl, width, height], 'theta': theta}

        return resp

    def get_neighboring_viewpoints(self, include_self=True):
        coord = Annotation.viewpoint_to_coord(self.viewpoint)
        if not coord:
            return None
        vps = set()
        for x in range(3):
            for y in range(3):
                for z in range(3):
                    # skip ourself
                    if x == y == z == 1:
                        continue
                    new_c = [
                        coord[0] + x - 1,
                        coord[1] + y - 1,
                        coord[2] + z - 1,
                    ]
                    # must be co-planar (drop diagonal corners)
                    if not (
                        coord[0] == new_c[0]
                        or coord[1] == new_c[1]
                        or coord[2] == new_c[2]
                    ):
                        continue
                    # this excludes neighbor center pieces when we are a center piece
                    if coord.count(0) == 2 and new_c.count(0) == 2:
                        continue
                    try:
                        vp = self.coord_to_viewpoint(new_c)
                        if vp:
                            vps.add(vp)
                    except ValueError:
                        # we just ignore out of range, as its floating in space
                        pass
        # corners have 6, the rest have 8
        assert (coord.count(0) == 0 and len(vps) == 6) or len(vps) == 8
        if include_self:
            vps.add(self.viewpoint)
        return vps

    @classmethod
    def coord_to_viewpoint(cls, c):
        if not c or len(c) != 3:
            return None
        sub = [
            ['down', '', 'up'],
            ['back', '', 'front'],
            ['left', '', 'right'],
        ]
        vp = ''
        for i in range(3):
            if c[i] < -1 or c[i] > 1:
                raise ValueError(f'value at {i} out of range: {c[i]}')
            vp += sub[i][c[i] + 1]
        return vp

    @classmethod
    def viewpoint_to_coord(cls, vp):
        c = [0, 0, 0]
        if vp.startswith('up'):
            c[0] = 1
        elif vp.startswith('down'):
            c[0] = -1
        if 'front' in vp:
            c[1] = 1
        elif 'back' in vp:
            c[1] = -1
        if 'right' in vp:
            c[2] = 1
        elif 'left' in vp:
            c[2] = -1
        # this means it is not a direction-based viewpoint
        if c == [0, 0, 0]:
            return None
        return c

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.annotations.schemas import AnnotationElasticsearchSchema

        return AnnotationElasticsearchSchema

    def send_to_identification(self, matching_set_query=None):
        sighting = self.get_sighting()
        if not sighting:
            raise HoustonException(
                log,
                f'{self} requires a sighting to run send_to_identification()',
                obj=self,
            )
        sighting.validate_id_configs()
        job_count = sighting.send_annotation_for_identification(self, matching_set_query)
        return job_count
