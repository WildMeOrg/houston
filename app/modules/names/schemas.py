# -*- coding: utf-8 -*-
"""
Serialization schemas for Names resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Name


class BaseNameSchema(ModelSchema):
    """
    Base Name schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Name
        fields = (
            Name.guid.key,
            Name.context.key,
            Name.value.key,
        )
        dump_only = (Name.guid.key,)


class DetailedNameSchema(BaseNameSchema):
    """
    Detailed Name schema exposes all useful fields.
    """

    class Meta(BaseNameSchema.Meta):
        fields = BaseNameSchema.Meta.fields
        dump_only = BaseNameSchema.Meta.dump_only
