# -*- coding: utf-8 -*-
"""
Serialization schemas for Keywords resources RESTful API
----------------------------------------------------
"""


from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields 

from .models import Keyword


class BaseKeywordSchema(ModelSchema):
    """
    Base Keyword schema exposes only the most general fields.
    """
    usageCount = base_fields.Function(
                    lambda kw: kw.number_referenced_dependencies(), 
                    dump_only=True # This is a read-only field
                    )

    class Meta:
        # pylint: disable=missing-docstring
        model = Keyword
        fields = (
            Keyword.guid.key,
            Keyword.value.key,
            Keyword.source.key,
            'usageCount', 

        )
        dump_only = (Keyword.guid.key,)


class DetailedKeywordSchema(BaseKeywordSchema):
    """
    Detailed Keyword schema exposes all useful fields.
    """

    class Meta(BaseKeywordSchema.Meta):
        fields = BaseKeywordSchema.Meta.fields + (
            Keyword.created.key,
            Keyword.updated.key,
        )
        dump_only = BaseKeywordSchema.Meta.dump_only + (
            Keyword.created.key,
            Keyword.updated.key,
        )
