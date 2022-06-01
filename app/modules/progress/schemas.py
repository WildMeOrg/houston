# -*- coding: utf-8 -*-
"""
Serialization schemas for Progress resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields

from flask_restx_patched import ModelSchema

from .models import Progress


class BaseProgressSchema(ModelSchema):
    """
    Base Progress schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Progress
        fields = (
            Progress.guid.key,
            Progress.description.key,
            Progress.percentage.key,
            Progress.status.key,
            Progress.message.key,
            'skipped',
            'cancelled',
            'failed',
            'complete',
            'active',
            'idle',
            'inactive',
            'ahead',
            Progress.celery_guid.key,
            Progress.sage_guid.key,
            Progress.eta.key,
            Progress.created.key,
            Progress.updated.key,
        )
        dump_only = (
            Progress.guid.key,
            Progress.celery_guid.key,
            Progress.sage_guid.key,
            Progress.created.key,
            Progress.updated.key,
        )


class DetailedProgressSchema(BaseProgressSchema):
    """
    Detailed Progress schema exposes all useful fields.
    """

    steps = base_fields.Nested(
        BaseProgressSchema,
        many=True,
    )

    class Meta(BaseProgressSchema.Meta):
        fields = BaseProgressSchema.Meta.fields + (
            Progress.parent_guid.key,
            'steps',
        )
        dump_only = BaseProgressSchema.Meta.dump_only
