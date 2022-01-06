# -*- coding: utf-8 -*-
"""
Serialization schemas for Tasks resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Task


class BaseTaskSchema(ModelSchema):
    """
    Base Task schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Task
        fields = (
            Task.guid.key,
            Task.title.key,
        )
        dump_only = (Task.guid.key,)


class DetailedTaskSchema(BaseTaskSchema):
    """
    Detailed Task schema exposes all useful fields.
    """

    class Meta(BaseTaskSchema.Meta):
        fields = BaseTaskSchema.Meta.fields
        dump_only = BaseTaskSchema.Meta.dump_only
