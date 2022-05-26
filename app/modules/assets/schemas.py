# -*- coding: utf-8 -*-
"""
Serialization schemas for Assets resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from marshmallow import ValidationError

from app.extensions import ExtraValidationSchema
from app.extensions.git_store.schemas import BaseGitStoreSchema
from app.modules import is_module_enabled
from flask_restx_patched import ModelSchema

from .models import Asset


class BaseAssetSchema(ModelSchema):
    """
    Base Asset schema exposes only the most general fields.
    """

    dimensions = base_fields.Function(Asset.get_dimensions)

    class Meta:
        # pylint: disable=missing-docstring
        model = Asset
        fields = (
            Asset.guid.key,
            'filename',
            'src',
            'elasticsearchable',
            Asset.indexed.key,
        )
        dump_only = (Asset.guid.key,)


class DetailedAssetTableSchema(BaseAssetSchema):
    """
    Detailed Asset schema exposes all useful fields.
    """

    git_store = base_fields.Nested(BaseGitStoreSchema)

    tags = base_fields.Nested(
        'BaseKeywordSchema',
        many=True,
    )

    if is_module_enabled('missions'):
        tasks = base_fields.Nested(
            'BaseMissionTaskTableSchema',
            many=True,
        )

    class Meta(BaseAssetSchema.Meta):
        fields = BaseAssetSchema.Meta.fields + (
            Asset.created.key,
            Asset.updated.key,
            Asset.size_bytes.key,
            Asset.git_store.key,
            'dimensions',
            'annotation_count',
            'classifications',
            'tags',
        )
        if is_module_enabled('missions'):
            fields = fields + ('tasks',)

        dump_only = BaseAssetSchema.Meta.dump_only + (
            Asset.created.key,
            Asset.updated.key,
        )


class DetailedAssetSchema(BaseAssetSchema):
    """
    Detailed Asset schema exposes all useful fields.
    """

    git_store = base_fields.Nested(BaseGitStoreSchema)

    annotations = base_fields.Nested('DetailedAnnotationSchema', many=True)

    tags = base_fields.Nested(
        'BaseKeywordSchema',
        many=True,
    )

    class Meta(BaseAssetSchema.Meta):
        fields = BaseAssetSchema.Meta.fields + (
            Asset.created.key,
            Asset.updated.key,
            Asset.git_store.key,
            'annotations',
            'dimensions',
            'classifications',
            'tags',
        )

        dump_only = BaseAssetSchema.Meta.dump_only + (
            Asset.created.key,
            Asset.updated.key,
        )


class ExtendedAssetSchema(BaseAssetSchema):
    annotations = base_fields.Nested('BaseAnnotationSchema', many=True)

    class Meta(BaseAssetSchema.Meta):
        fields = BaseAssetSchema.Meta.fields + (
            Asset.created.key,
            Asset.updated.key,
            'annotations',
            'dimensions',
        )


class ExtendedAssetDetailedAnnotationsSchema(BaseAssetSchema):
    annotations = base_fields.Nested('DetailedAnnotationSchema', many=True)

    class Meta(BaseAssetSchema.Meta):
        fields = BaseAssetSchema.Meta.fields + (
            Asset.created.key,
            Asset.updated.key,
            'annotations',
            'dimensions',
        )


class DebugAssetSchema(DetailedAssetSchema):
    jobs = base_fields.Function(Asset.get_jobs_debug)

    class Meta(DetailedAssetSchema.Meta):
        fields = DetailedAssetSchema.Meta.fields + ('jobs',)


def not_negative(value):
    if value < 0:
        raise ValidationError('Value must be greater than 0.')


class PatchAssetSchema(ExtraValidationSchema):
    class AssetRotateSchema(ExtraValidationSchema):
        angle = base_fields.Integer(validate=not_negative)

    rotate = base_fields.Nested(AssetRotateSchema)
