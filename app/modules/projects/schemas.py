# -*- coding: utf-8 -*-
"""
Serialization schemas for Projects resources RESTful API
----------------------------------------------------
"""

from flask_restplus_patched import ModelSchema

from .models import Project


class BaseProjectSchema(ModelSchema):
    """
    Base Project schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Project
        fields = (
            Project.guid.key,
            Project.title.key,
        )
        dump_only = (Project.guid.key,)


class DetailedProjectSchema(BaseProjectSchema):
    """
    Detailed Project schema exposes all useful fields.
    """

    class Meta(BaseProjectSchema.Meta):
        fields = BaseProjectSchema.Meta.fields
        dump_only = BaseProjectSchema.Meta.dump_only
