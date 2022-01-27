# -*- coding: utf-8 -*-
"""
Serialization schemas for Assets resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from marshmallow import ValidationError
from app.extensions.git_store import GitStore

from flask_restx_patched import ModelSchema
from app.extensions import ExtraValidationSchema

from .models import Asset


class BaseAssetSchema(ModelSchema):
    """
    Base Asset schema exposes only the most general fields.
    """

    dimensions = base_fields.Function(Asset.get_dimensions)

    class Meta:
        # pylint: disable=missing-docstring
        model = Asset
        fields = (Asset.guid.key, 'filename', 'src')
        dump_only = (Asset.guid.key,)


class DetailedAssetTableSchema(BaseAssetSchema):
    """
    Detailed Asset schema exposes all useful fields.
    """

    tags = base_fields.Nested(
        'BaseKeywordSchema',
        many=True,
    )

    class Meta(BaseAssetSchema.Meta):
        fields = BaseAssetSchema.Meta.fields + (
            Asset.created.key,
            Asset.updated.key,
            Asset.size_bytes.key,
            'dimensions',
            'annotation_count',
            'classifications',
            'tags',
        )

        dump_only = BaseAssetSchema.Meta.dump_only + (
            Asset.created.key,
            Asset.updated.key,
        )


class DetailedAssetSchema(BaseAssetSchema):
    """
    Detailed Asset schema exposes all useful fields.
    """

    git_store = base_fields.Nested('BaseGitStoreSchema')

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


def not_negative(value):
    if value < 0:
        raise ValidationError('Value must be greater than 0.')


class PatchAssetSchema(ExtraValidationSchema):
    class AssetRotateSchema(ExtraValidationSchema):
        angle = base_fields.Integer(validate=not_negative)

    rotate = base_fields.Nested(AssetRotateSchema)


class BaseGitStoreSchema(ModelSchema):
    """
    Base Git Store schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = GitStore
        fields = (
            GitStore.guid.key,
            GitStore.commit.key,
            GitStore.major_type.key,
            GitStore.description.key,
        )
        dump_only = (
            GitStore.guid.key,
            GitStore.commit.key,
        )


class CreateGitStoreSchema(BaseGitStoreSchema):
    """
    Detailed Git Store schema exposes all useful fields.
    """

    class Meta(BaseGitStoreSchema.Meta):
        fields = BaseGitStoreSchema.Meta.fields + (
            GitStore.owner_guid.key,
            GitStore.created.key,
            GitStore.updated.key,
        )
        dump_only = BaseGitStoreSchema.Meta.dump_only + (
            GitStore.owner_guid.key,
            GitStore.created.key,
            GitStore.updated.key,
        )


class DetailedGitStoreSchema(CreateGitStoreSchema):
    """
    Detailed Git Store schema exposes all useful fields.
    """

    from app.modules.assets.models import Asset

    assets = base_fields.Nested(
        'BaseAssetSchema',
        exclude=Asset.git_store_guid.key,
        many=True,
    )

    class Meta(CreateGitStoreSchema.Meta):
        fields = CreateGitStoreSchema.Meta.fields + ('assets',)
        dump_only = CreateGitStoreSchema.Meta.dump_only
