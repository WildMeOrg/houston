# -*- coding: utf-8 -*-
"""
Serialization schemas for Names resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from .models import Name
from app.modules.users.schemas import PublicUserSchema


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
            'elasticsearchable',
            Name.indexed.key,
        )
        dump_only = (Name.guid.key,)


class DetailedNameSchema(BaseNameSchema):
    """
    Detailed Name schema exposes all useful fields.
    """

    creator = base_fields.Nested(
        PublicUserSchema,
        attribute='creator',
        many=False,
    )
    preferring_users = base_fields.Nested(
        PublicUserSchema,
        attribute='get_preferring_users',
        many=True,
    )

    class Meta(BaseNameSchema.Meta):
        fields = BaseNameSchema.Meta.fields + (
            Name.creator.key,
            'preferring_users',
        )
        dump_only = BaseNameSchema.Meta.dump_only
