# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

import logging
import uuid

from app.extensions import HoustonModel, db
from app.modules.bounded_annotation.models import BoundedAnnotation

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class ScoutAnnotationKeywords(db.Model, HoustonModel):
    annotation_guid = db.Column(
        db.GUID, db.ForeignKey('scout_annotation.guid'), primary_key=True
    )
    keyword_guid = db.Column(db.GUID, db.ForeignKey('keyword.guid'), primary_key=True)
    annotation = db.relationship('ScoutAnnotation', back_populates='keyword_refs')
    keyword = db.relationship('Keyword')


class ScoutAnnotation(db.Model, BoundedAnnotation):
    # task_guid = db.Column(
    #     db.GUID,
    #     db.ForeignKey('mission_task.guid', ondelete='CASCADE'),
    #     index=True,
    #     nullable=True,
    # )
    # task = db.relationship(
    #     'MissionTask',
    #     backref=db.backref(
    #         'annotations',
    #         primaryjoin='MissionTask.guid == ScoutAnnotation.task_guid',
    #         order_by='ScoutAnnotation.guid',
    #     ),
    # )

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    asset_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset.guid', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    # asset = db.relationship('Asset', back_populates='annotations')

    keyword_refs = db.relationship('ScoutAnnotationKeywords')

    contributor_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    # contributor = db.relationship('User', back_populates='contributed_annotations')

    inExport = db.Column(db.Boolean, default=True, nullable=True)

    def get_sage_name(self):
        from app.extensions.sage import SAGE_UNKNOWN_NAME

        return SAGE_UNKNOWN_NAME

    # Scout has no AGS so it's debug for Annotation will be drastically simpler
    def get_debug_json(self):
        from .schemas import DetailedAnnotationSchema

        annot_schema = DetailedAnnotationSchema()

        return {'annotation': annot_schema.dump(self).data}

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
        rel = ScoutAnnotationKeywords(annotation=self, keyword=keyword)
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

    def get_keyword_values(self):
        if not self.keyword_refs:
            return []
        return sorted(ref.keyword.value for ref in self.keyword_refs)
