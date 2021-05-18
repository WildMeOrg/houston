# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

from app.extensions import db, HoustonModel
from app.modules.keywords.models import Keyword, KeywordSource

import uuid
import logging
import json

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AnnotationKeywords(db.Model, HoustonModel):
    annotation_guid = db.Column(
        db.GUID, db.ForeignKey('annotation.guid'), primary_key=True
    )
    keyword_guid = db.Column(db.GUID, db.ForeignKey('keyword.guid'), primary_key=True)
    annotation = db.relationship('Annotation', back_populates='keywords')
    keyword = db.relationship('Keyword')


class Annotation(db.Model, HoustonModel):
    """
    Annotations database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    asset_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset.guid', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    asset = db.relationship('Asset', backref=db.backref('annotations'))

    encounter_guid = db.Column(
        db.GUID,
        db.ForeignKey('encounter.guid', ondelete='CASCADE'),
        index=True,
        nullable=True,
    )
    encounter = db.relationship('Encounter', backref=db.backref('annotations'))
    keywords = db.relationship('AnnotationKeywords')

    # May have multiple jobs outstanding, store as Json obj uuid_str is key, In_progress Bool is value
    jobs = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def get_keywords(self):
        return [ref.keyword for ref in self.keywords]

    def add_keyword(self, keyword):
        with db.session.begin(subtransactions=True):
            self.add_keyword_in_context(keyword)

    def add_new_keyword(self, value, source=KeywordSource.user):
        with db.session.begin(subtransactions=True):
            keyword = Keyword(value=value, source=source)
            db.session.add(keyword)
            self.add_keyword_in_context(keyword)
        return keyword

    def add_keywords(self, keyword_list):
        with db.session.begin():
            for keyword in keyword_list:
                self.add_keyword_in_context(keyword)

    def add_keyword_in_context(self, keyword):
        # TODO disallow duplicates
        rel = AnnotationKeywords(annotation=self, keyword=keyword)
        db.session.add(rel)
        self.keywords.append(rel)

    def delete(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)

    def check_job_status(self, job_id):
        job_id_str = str(job_id)
        decoded_jobs = json.loads(self.jobs)
        if job_id_str not in decoded_jobs.keys():
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False
        if decoded_jobs[job_id_str]:
            log.warning(f'check_job_status called for completed job {job_id}')
            return False

        # TODO Poll ACM to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True
