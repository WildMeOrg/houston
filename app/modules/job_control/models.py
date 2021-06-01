# -*- coding: utf-8 -*-
"""Provides UI space served directly from this application"""

import logging
from app.extensions import db, HoustonModel
import uuid

log = logging.getLogger(__name__)


# Jobs are only supported on specific classes at the moment
class JobControl(db.Model, HoustonModel):
    guid = db.Column(db.GUID, default=uuid.uuid4, primary_key=True)
    asset_group_sighting_uuid = db.Column(db.GUID, nullable=True)
    annotation_uuid = db.Column(db.GUID, nullable=True)

    def delete(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)

    @classmethod
    def delete_job(cls, job_uuid):
        job = JobControl.query.get(job_uuid)
        if job:
            job.delete()

    @classmethod
    def add_asset_group_sighting_job(cls, job_uuid, obj_uuid):
        new_job = JobControl(guid=job_uuid, asset_group_sighting_uuid=obj_uuid)
        with db.session.begin(subtransactions=True):
            db.session.add(new_job)

    @classmethod
    def add_annotation_job(cls, job_uuid, obj_uuid):
        new_job = JobControl(guid=job_uuid, annotation_uuid=obj_uuid)
        with db.session.begin(subtransactions=True):
            db.session.add(new_job)

    # Called by a periodic background task, TODO
    @classmethod
    def periodic(cls):
        for job in JobControl.query.all():
            job.process()

    def process(self):
        type_str = ''
        obj_uuid = None
        job_obj = None
        if self.asset_group_sighting_uuid:
            from app.modules.asset_groups.models import AssetGroupSighting

            obj_uuid = self.asset_group_sighting_uuid
            type_str = 'AssetGroupSighting'
            job_obj = AssetGroupSighting.query.get(obj_uuid)
        elif self.annotation_uuid:
            from app.modules.annotations.models import Annotation

            type_str = 'Annotation'
            obj_uuid = self.annotation_uuid
            job_obj = Annotation.query.get(obj_uuid)
        else:
            log.warning('Job created without any obj uuid, deleting')
            self.delete()
            return

        if not job_obj:
            log.warning(f'{type_str} {obj_uuid} removed')
            self.delete()
            return

        if not job_obj.check_job_status(self.guid):
            self.delete()
            return
