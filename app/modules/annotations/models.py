# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

from app.extensions import db, HoustonModel
from app.modules import is_module_enabled
from app.utils import HoustonException

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
                log, f'Annotation {self.guid} not connected to an encounter'
            )

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
