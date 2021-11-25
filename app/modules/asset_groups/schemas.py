# -*- coding: utf-8 -*-
"""
Serialization schemas for Asset_groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema
from app.modules.assets.schemas import DetailedAssetGroupAssetSchema
from app.modules.sightings.schemas import AugmentedEdmSightingSchema

from .models import AssetGroup, AssetGroupSighting

# We need api endpoints for AssetGroupSightings which behave just like the
# Sighting endpoints to standardize frontend interactions. For that reason we need
# to know which sighting fields to expect in an AssetGroupSighting.config dict
SIGHTING_FIELDS_IN_AGS_CONFIG = {
    'startTime',
    'decimalLatitude',
    'decimalLongitude',
    'encounters',
    'locationId',
    'verbatimLocality',
    'encounterCounts',
    'id',
    'comments',
    'featuredAssetGuid',
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

    assets = base_fields.Nested(
        DetailedAssetGroupAssetSchema,
        attribute='get_assets',
        many=True,
    )

    completion = base_fields.Function(AssetGroupSighting.get_completion)
    sighting_guid = base_fields.Function(AssetGroupSighting.get_sighting_guid)

    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)

    class Meta(BaseAssetGroupSightingSchema.Meta):

        fields = BaseAssetGroupSightingSchema.Meta.fields + (
            AssetGroupSighting.stage.key,
            AssetGroupSighting.config.key,
            'assets',
            'completion',
            'creator',
            'sighting_guid',
            AssetGroupSighting.jobs.key,
            AssetGroupSighting.asset_group_guid.key,
        )
        dump_only = BaseAssetGroupSightingSchema.Meta.dump_only + (
            AssetGroupSighting.jobs.key,
        )


class AssetGroupSightingEncounterSchema(ModelSchema):
    createdHouston = base_fields.DateTime()
    customFields = base_fields.Dict(default={})
    decimalLatitude = base_fields.Float(default=None)
    decimalLongitude = base_fields.Float(default=None)
    guid = base_fields.UUID()
    hasEdit = base_fields.Boolean(default=True)
    hasView = base_fields.Boolean(default=True)
    id = base_fields.UUID(attribute='guid')
    individual = base_fields.Dict(default={})
    locationId = base_fields.String(default=None)
    owner = base_fields.Dict()
    sex = base_fields.String(default=None)
    submitter = base_fields.Dict(default=None)
    taxonomy = base_fields.Dict(default={})
    time = base_fields.String(default=None)
    updatedHouston = base_fields.DateTime()
    version = base_fields.String(default=None)


class AssetGroupSightingAsSightingSchema(AugmentedEdmSightingSchema):
    """
    In order for the frontend to render an AGS with the same code that renders a
    sighting, we have to pop out all the fields in AGS.config into the top-level
    of the schema. This is done with AssetGroupSighting.config_field_getter,
    which creates a getter for a config field of a given name. We can add more
    fields using the pattern below.
    """

    completion = base_fields.Function(AssetGroupSighting.get_completion)
    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)
    # Note: these config_field_getter vars should conform to SIGHTING_FIELDS_IN_AGS_CONFIG
    # at the top of this file
    startTime = base_fields.Function(AssetGroupSighting.config_field_getter('startTime'))
    encounters = base_fields.Nested(
        AssetGroupSightingEncounterSchema,
        attribute='get_encounters',
        many=True,
    )
    decimalLatitude = base_fields.Function(
        AssetGroupSighting.config_field_getter('decimalLatitude', cast=float)
    )
    decimalLongitude = base_fields.Function(
        AssetGroupSighting.config_field_getter('decimalLongitude', cast=float)
    )
    locationId = base_fields.Function(
        AssetGroupSighting.config_field_getter('locationId', default='')
    )
    verbatimLocality = base_fields.Function(
        AssetGroupSighting.config_field_getter('verbatimLocality', default='')
    )
    id = base_fields.UUID(attribute='guid')
    encounterCounts = base_fields.Function(
        AssetGroupSighting.config_field_getter('encounterCounts', default={})
    )
    featuredAssetGuid = base_fields.Function(
        AssetGroupSighting.config_field_getter('featuredAssetGuid')
    )
    sightingGuid = base_fields.Function(AssetGroupSighting.get_sighting_guid)
    comments = base_fields.Function(
        AssetGroupSighting.config_field_getter('comments', default=None)
    )
    # These are fields that are in Sighting but don't exist for
    # AssetGroupSighting
    createdEDM = base_fields.DateTime(default=None)
    customFields = base_fields.Dict(attribute='get_custom_fields')
    version = base_fields.String(default=None)

    class Meta:
        # adds 'stage' to the fields already defined above
        additional = ('stage', 'asset_group_guid')
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
