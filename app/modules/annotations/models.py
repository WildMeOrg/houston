# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

from app.extensions import db, FeatherModel

import uuid
import logging
import json

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Annotation(db.Model, FeatherModel):
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

    # May have multiple jobs outstanding, store as Json obj uuid_str is key, In_progress Bool is value
    jobs = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

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
