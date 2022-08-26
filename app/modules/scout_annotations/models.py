# -*- coding: utf-8 -*-
"""
￼Annotations database models
￼--------------------
￼"""

import logging

from app.extensions import db
from app.modules.annotations.models import Annotation

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class ScoutAnnotation(Annotation):

    # Asset group did this for Gitstore but if ScoutAnnotation does it blows up
    # guid = db.Column(db.GUID, db.ForeignKey('annotation.guid'), primary_key=True)
    task_guid = db.Column(
        db.GUID,
        db.ForeignKey('mission_task.guid', ondelete='CASCADE'),
        index=True,
        nullable=True,
    )
    task = db.relationship(
        'MissionTask',
        backref=db.backref(
            'annotations',
            primaryjoin='MissionTask.guid == ScoutAnnotation.task_guid',
            order_by='ScoutAnnotation.guid',
        ),
    )

    inExport = db.Column(db.Boolean, default=True, nullable=True)

    def get_sage_name(self):
        from app.extensions.sage import SAGE_UNKNOWN_NAME

        return SAGE_UNKNOWN_NAME

    # Scout has no AGS so it's debug for Annotation will be drastically simpler
    def get_debug_json(self):
        from .schemas import DetailedAnnotationSchema

        annot_schema = DetailedAnnotationSchema()

        return {'annotation': annot_schema.dump(self).data}
