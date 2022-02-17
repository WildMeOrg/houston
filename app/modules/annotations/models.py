# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

from app.extensions import db, HoustonModel
from app.modules import is_module_enabled
from app.utils import HoustonException
from flask import current_app

import uuid
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AnnotationKeywords(db.Model, HoustonModel):
    annotation_guid = db.Column(
        db.GUID, db.ForeignKey('annotation.guid'), primary_key=True
    )
    keyword_guid = db.Column(db.GUID, db.ForeignKey('keyword.guid'), primary_key=True)
    annotation = db.relationship('Annotation', back_populates='keyword_refs')
    keyword = db.relationship('Keyword')


class Annotation(db.Model, HoustonModel):
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

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.annotations.schemas import DetailedAnnotationSchema

        return DetailedAnnotationSchema

    def get_job_debug(self, verbose):
        if self.encounter:
            return self.encounter.sighting.get_job_debug(self.guid, verbose)
        else:
            raise HoustonException(
                log, f'Annotation {self.guid} not connected to an encounter'
            )

    # Assumes that the caller actually wants the debug data for the context of where the annotation came from.
    # Therefore returns the debug data for the sighting (if there is one), the ags if not.
    # If neither Sighting or AGS (Annot created but not curated), returns the DetailedAnnot data
    def get_debug_json(self):
        if self.encounter:
            return self.encounter.sighting.get_debug_sighting_json()

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

    def ensure_sage(self):
        assert self.asset
        if not self.asset.content_guid:
            log.warning(
                f'Not adding Annot {self.guid} to Sage as its asset has no content guid'
            )
            return
        from app.extensions.acm import (
            to_acm_uuid,
            from_acm_uuid,
            default_acm_individual_uuid,
            encode_acm_request,
        )

        sage_req = {
            'image_uuid_list': [to_acm_uuid(self.asset.content_guid)],
            'annot_species_list': [self.ia_class],
            'annot_bbox_list': [self.bounds['rect']],
            'annot_name_list': [default_acm_individual_uuid()],
            'annot_theta_list': [self.bounds['theta']],
        }
        if self.encounter and self.encounter.individual:
            sage_req['annot_name_list'][0] = to_acm_uuid(self.encounter.individual.guid)

        encoded_request = encode_acm_request(sage_req)
        # as does this
        sage_response = current_app.acm.request_passthrough_result(
            'annotations.create',
            'post',
            {'params': encoded_request},
        )
        self.content_guid = from_acm_uuid(sage_response[0])

    @property
    def keywords(self):
        return self.get_keywords()

    def get_keywords(self):
        return sorted([ref.keyword for ref in self.keyword_refs])

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
        return user is not None and user == self.asset.git_store.owner

    # Used for building matching set but abstract the annotation to name mapping
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

    def get_matching_set(self, criteria=None):
        if not self.encounter_guid:
            raise ValueError(f'{self} has no Encounter so cannot be matched against')
        if not criteria or not isinstance(criteria, dict):
            criteria = {}
        if 'viewpoint' not in criteria:
            criteria['viewpoint'] = self.get_neighboring_viewpoints()

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
