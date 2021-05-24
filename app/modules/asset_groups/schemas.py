# -*- coding: utf-8 -*-
"""
Serialization schemas for Asset_groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import AssetGroup, AssetGroupSighting


class AssetGroupSightingSchema(ModelSchema):
    """
    Asset_group sighting schema
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = AssetGroupSighting
        fields = (AssetGroupSighting.guid.key,)
        dump_only = (AssetGroupSighting.guid.key,)


class BaseAssetGroupSchema(ModelSchema):
    """
    Base Asset_group schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = AssetGroup
        fields = (
            AssetGroup.guid.key,
            AssetGroup.commit.key,
            AssetGroup.major_type.key,
            AssetGroup.description.key,
        )
        dump_only = (
            AssetGroup.guid.key,
            AssetGroup.commit.key,
            AssetGroup.is_processed.__name__,
        )


class CreateAssetGroupSchema(BaseAssetGroupSchema):
    """
    Detailed Asset_group schema exposes all useful fields.
    """

    class Meta(BaseAssetGroupSchema.Meta):
        fields = BaseAssetGroupSchema.Meta.fields + (
            AssetGroup.owner_guid.key,
            AssetGroup.created.key,
            AssetGroup.updated.key,
        )
        dump_only = BaseAssetGroupSchema.Meta.dump_only + (
            AssetGroup.owner_guid.key,
            AssetGroup.created.key,
            AssetGroup.updated.key,
        )


class DetailedAssetGroupSchema(CreateAssetGroupSchema):
    """
    Detailed Asset_group schema exposes all useful fields.
    """

    from app.modules.assets.models import Asset

    assets = base_fields.Nested(
        'BaseAssetSchema',
        exclude=Asset.asset_group_guid.key,
        many=True,
    )
    sightings = base_fields.Nested(
        'AssetGroupSightingSchema',
        many=True,
    )

    class Meta(CreateAssetGroupSchema.Meta):
        fields = CreateAssetGroupSchema.Meta.fields + ('assets', 'sightings')
        dump_only = CreateAssetGroupSchema.Meta.dump_only
