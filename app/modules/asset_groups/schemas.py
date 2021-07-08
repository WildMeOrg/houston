# -*- coding: utf-8 -*-
"""
Serialization schemas for Asset_groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import AssetGroup, AssetGroupSighting


class BaseAssetGroupSightingSchema(ModelSchema):
    """
    Asset_group sighting schema
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = AssetGroupSighting
        fields = (AssetGroupSighting.guid.key,)
        dump_only = (AssetGroupSighting.guid.key,)


class DetailedAssetGroupSightingSchema(BaseAssetGroupSightingSchema):
    """
    Detailed Asset_group_sighting schema exposes all useful fields.
    """

    class Meta(BaseAssetGroupSightingSchema.Meta):
        fields = BaseAssetGroupSightingSchema.Meta.fields + (
            AssetGroupSighting.stage.key,
            AssetGroupSighting.config.key,
            AssetGroupSighting.assets.__name__,
        )
        dump_only = BaseAssetGroupSightingSchema.Meta.dump_only


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
    asset_group_sightings = base_fields.Nested(
        'BaseAssetGroupSightingSchema',
        many=True,
    )

    class Meta(CreateAssetGroupSchema.Meta):
        fields = CreateAssetGroupSchema.Meta.fields + ('assets', 'asset_group_sightings')
        dump_only = CreateAssetGroupSchema.Meta.dump_only
