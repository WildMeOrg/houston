# -*- coding: utf-8 -*-
"""
Serialization schemas for Assets resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import Asset


class BaseAssetSchema(ModelSchema):
    """
    Base Asset schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Asset
        fields = (
            Asset.guid.key,
            'filename',
        )
        dump_only = (Asset.guid.key,)


class DetailedAssetSchema(BaseAssetSchema):
    """
    Detailed Asset schema exposes all useful fields.
    """

    submission = base_fields.Nested('BaseSubmissionSchema')

    class Meta(BaseAssetSchema.Meta):
        fields = BaseAssetSchema.Meta.fields + (
            Asset.created.key,
            Asset.updated.key,
            Asset.submission.key,
            'filename',
            'src',
        )
        dump_only = BaseAssetSchema.Meta.dump_only + (
            Asset.created.key,
            Asset.updated.key,
        )
