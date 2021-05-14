# -*- coding: utf-8 -*-
"""
Serialization schemas for Keywords resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import Keyword


class BaseKeywordSchema(ModelSchema):
    """
    Base Keyword schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Keyword
        fields = (
            Keyword.guid.key,
            Keyword.value.key,
            Keyword.source.key,
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
