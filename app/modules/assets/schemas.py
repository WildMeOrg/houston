# -*- coding: utf-8 -*-
"""
Serialization schemas for Assets resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from marshmallow import ValidationError

from flask_restx_patched import ModelSchema
from app.extensions import ExtraValidationSchema

from .models import Asset


class BaseAssetSchema(ModelSchema):
    """
    Base Asset schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Asset
        fields = (Asset.guid.key, 'filename', 'src')
        dump_only = (Asset.guid.key,)


class DetailedAssetSchema(BaseAssetSchema):
    """
    Detailed Asset schema exposes all useful fields.
    """

    asset_group = base_fields.Nested('BaseAssetGroupSchema')
    annotations = base_fields.Nested('DetailedAnnotationSchema', many=True)

    class Meta(BaseAssetSchema.Meta):
        fields = BaseAssetSchema.Meta.fields + (
            Asset.created.key,
            Asset.updated.key,
            Asset.asset_group.key,
            'annotations',
            'dimensions',
        )
        dump_only = BaseAssetSchema.Meta.dump_only + (
            Asset.created.key,
            Asset.updated.key,
        )


class DetailedAssetGroupAssetSchema(BaseAssetSchema):
    fields = BaseAssetSchema.Meta.fields + (
        Asset.created.key,
        Asset.updated.key,
        'annotations',
        'dimensions',
    )


def not_negative(value):
    if value < 0:
        raise ValidationError('Value must be greater than 0.')


class PatchAssetSchema(ExtraValidationSchema):
    class AssetRotateSchema(ExtraValidationSchema):
        angle = base_fields.Integer(validate=not_negative)

    rotate = base_fields.Nested(AssetRotateSchema)
