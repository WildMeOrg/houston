# -*- coding: utf-8 -*-
"""
Serialization schemas for Progress resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Progress


class BaseProgressSchema(ModelSchema):
    """
    Base Progress schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Progress
        fields = (Progress.guid.key,)
        dump_only = (Progress.guid.key,)


class DetailedProgressSchema(BaseProgressSchema):
    """
    Detailed Progress schema exposes all useful fields.
    """

    class Meta(BaseProgressSchema.Meta):
        fields = BaseProgressSchema.Meta.fields + (
            Progress.description.key,
            Progress.percentage.key,
            Progress.status.key,
            Progress.message.key,
            'complete',
            'ahead',
            Progress.parent_guid.key,
            Progress.eta.key,
            Progress.created.key,
            Progress.updated.key,
        )
        dump_only = BaseProgressSchema.Meta.dump_only + (
            Progress.created.key,
            Progress.updated.key,
        )
