# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

import logging
import uuid

from flask import current_app

from app.extensions import HoustonModel, SageModel, db
from app.modules import is_module_enabled
from app.utils import HoustonException

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AnnotationKeywords(db.Model, HoustonModel):
    annotation_guid = db.Column(
        db.GUID, db.ForeignKey('annotation.guid'), primary_key=True
    )
    keyword_guid = db.Column(db.GUID, db.ForeignKey('keyword.guid'), primary_key=True)
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
        result = {'no_content_guid': []}

        # Annots must always have a content guid
        no_contents = Annotation.query.filter(Annotation.content_guid.is_(None)).all()
        if no_contents:
            result['no_content_guid'] = [annot.guid for annot in no_contents]

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
            log.error(
                'Annotation {!r} has no asset, cannot send annotation to Sage'.format(
                    self
                )
            )

            return

        # First, ensure that the annotation's asset has been synced with Sage
        if not skip_asset:
            self.asset.sync_with_sage(
                ensure=ensure, force=force, bulk_sage_uuids=bulk_sage_uuids, **kwargs
            )

        if self.asset.content_guid is None:
            log.error(
                'Asset for Annotation %r failed to send, cannot send annotation to Sage'
                % (self,)
            )
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
            log.error(
                'Annotation %r failed to pass validate_bounds(), cannot send annotation to Sage'
                % (self,)
            )
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
            if not overwrite:
                log.warning(
                    'Annotation %r already has a progress identification %r'
                    % (
                        self,
                        self.progress_identification,
                    )
                )
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
    # Therefore returns the debug data for the sighting (if there is one), the ags if not.
    # If neither Sighting or AGS (Annot created but not curated), returns the DetailedAnnot data
    def get_debug_json(self):
        if self.encounter:
            return self.encounter.sighting.get_debug_json()

        assert self.asset.git_store
        ags = self.asset.git_store.get_asset_group_sighting_for_annotation(self)
        if ags:
            from app.modules.asset_groups.schemas import DebugAssetGroupSightingSchema

            schema = DebugAssetGroupSightingSchema()
            return schema.dump(ags).data
        else:
            # Annotation created but not curated into an AGS
            from .schemas import DetailedAnnotationSchema

            schema = DetailedAnnotationSchema()
            return schema.dump(self).data

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

        Annotation.sync_all_with_sage(ensure=True)

        return matching_set

    def get_matching_set_default_query(self):
        # n.b. default will not take any locationId or ownership into consideration
        parts = {'filter': []}

        viewpoint_list = self.get_neighboring_viewpoints()
        # TODO should we allow nulls?
        if viewpoint_list:
            viewpoint_data = []
            for vp in viewpoint_list:
                viewpoint_data.append({'term': {'viewpoint': vp}})
            parts['filter'].append(
                {
                    'bool': {
                        'minimum_should_match': 1,
                        'should': viewpoint_data,
                    }
                }
            )

        # same, re: nulls
        tx_guid = self.get_taxonomy_guid()
        if tx_guid:
            parts['filter'].append({'match': {'taxonomy_guid': tx_guid}})

        if self.encounter_guid:
            parts['must_not'] = {'match': {'encounter_guid': str(self.encounter_guid)}}

        return {'bool': parts}

    # this is to allow for manipulation of a user-provided query prior to actually using it
    #  e.g. we might want to _force_ criteria or remove certain filters, etc.
    def resolve_matching_set_query(self, query):
        if not query or not isinstance(query, dict):
            raise ValueError('must be passed a dict ES query')
        if not self.encounter_guid:
            raise ValueError('cannot resolve query on Annotation with no Encounter')
        # we just punt on stuff we dont understand and accept as-is
        if (
            'bool' not in query
            or not isinstance(query['bool'], dict)
            or 'filter' not in query['bool']
        ):
            log.debug(f'not resolving atypical query: {query}')
            return query
        # handle case where we have {bool: {filter: {...}} to make filter an array
        if not isinstance(query['bool']['filter'], list):
            query['bool']['filter'] = [query['bool']['filter']]
        # i guess to be *extra-thorough* this should *update* an existing `must_not` ?
        # we do not match within our own encounter
        if 'must_not' not in query['bool']:
            query['bool']['must_not'] = {
                'match': {'encounter_guid': str(self.encounter_guid)}
            }
        # (going with the theory that if these are *redundant* its not a big deal to ES.)
        # we MUST have a content_guid
        query['bool']['filter'].append({'exists': {'field': 'content_guid'}})
        return query

    # first tries encounter fields, but will use field on sighting if none on encounter,
    #   unless sighting_fallback=False
    def get_location_id(self, sighting_fallback=True):
        return (
            self.encounter.get_location_id(sighting_fallback)
            if self.encounter_guid
            else None
        )

    def get_taxonomy_guid(self, sighting_fallback=True):
        return (
            self.encounter.get_taxonomy_guid(sighting_fallback)
            if self.encounter_guid
            else None
        )

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

    def get_keyword_values(self):
        if not self.keyword_refs:
            return []
        return sorted(ref.keyword.value for ref in self.keyword_refs)

    def delete(self):
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
