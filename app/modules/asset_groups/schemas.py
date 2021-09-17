# -*- coding: utf-8 -*-
"""
Serialization schemas for Asset_groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import AssetGroup, AssetGroupSighting

# We need api endpoints for AssetGroupSightings which behave just like the
# Sighting endpoints to standardize frontend interactions. For that reason we need
# to know which sighting fields to expect in an AssetGroupSighting.config dict
SIGHTING_FIELDS_IN_AGS_CONFIG = {
    'decimalLatitude',
    'decimalLongitude',
    'encounters',
    'locationId',
    'startTime',
}


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

    assets = base_fields.Function(AssetGroupSighting.get_assets)

    completion = base_fields.Function(AssetGroupSighting.get_completion)

    class Meta(BaseAssetGroupSightingSchema.Meta):

        fields = BaseAssetGroupSightingSchema.Meta.fields + (
            AssetGroupSighting.stage.key,
            AssetGroupSighting.config.key,
            'assets',
            'completion',
        )
        dump_only = BaseAssetGroupSightingSchema.Meta.dump_only


class AssetGroupSightingAsSightingSchema(BaseAssetGroupSightingSchema):
    """
    In order for the frontend to render an AGS with the same code that renders a
    sighting, we have to pop out all the fields in AGS.config into the top-level
    of the schema. This is done with AssetGroupSighting.config_field_getter,
    which creates a getter for a config field of a given name. We can add more
    fields using the pattern below.
    """

    assets = base_fields.Function(AssetGroupSighting.get_assets)
    completion = base_fields.Function(AssetGroupSighting.get_completion)

    # Note: these config_field_getter vars should conform to SIGHTING_FIELDS_IN_AGS_CONFIG
    # at the top of this file
    decimalLatitude = base_fields.Function(
        AssetGroupSighting.config_field_getter('decimalLatitude')
    )
    decimalLongitude = base_fields.Function(
        AssetGroupSighting.config_field_getter('decimalLongitude')
    )
    locationId = base_fields.Function(
        AssetGroupSighting.config_field_getter('locationId')
    )
    startTime = base_fields.Function(AssetGroupSighting.config_field_getter('startTime'))
    encounters = base_fields.Function(
        AssetGroupSighting.config_field_getter('encounters')
    )

    class Meta(BaseAssetGroupSightingSchema.Meta):
        fields = BaseAssetGroupSightingSchema.Meta.fields + (
            AssetGroupSighting.stage.key,
            'assets',
            'completion',
            'decimalLatitude',
            'decimalLongitude',
            'locationId',
            'startTime',
            'encounters',
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
