# -*- coding: utf-8 -*-
"""
Serialization schemas for Asset_groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema
from app.modules.assets.schemas import ExtendedAssetDetailedAnnotationsSchema

from .models import AssetGroup, AssetGroupSighting

# We need api endpoints for AssetGroupSightings which behave just like the
# Sighting endpoints to standardize frontend interactions. For that reason we need
# to know which sighting fields to expect in an AssetGroupSighting.config dict
SIGHTING_FIELDS_IN_AGS_CONFIG = {
    'time',
    'timeSpecificity',
    'decimalLatitude',
    'decimalLongitude',
    'encounters',
    'locationId',
    'verbatimLocality',
    'verbatimEventDate',
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


class DetailedAssetGroupSightingJobSchema(ModelSchema):
    job_id = base_fields.String()
    model = base_fields.String()
    active = base_fields.Boolean()
    start = base_fields.DateTime()
    asset_ids = base_fields.List(base_fields.String)


class DebugAssetGroupSightingJobSchema(DetailedAssetGroupSightingJobSchema):
    json_result = base_fields.Dict()


class DetailedAssetGroupSightingSchema(BaseAssetGroupSightingSchema):
    """
    Detailed Asset_group_sighting schema exposes all useful fields.
    """

    assets = base_fields.Nested(
        ExtendedAssetDetailedAnnotationsSchema,
        attribute='get_assets',
        many=True,
    )

    completion = base_fields.Function(AssetGroupSighting.get_completion)
    sighting_guid = base_fields.Function(AssetGroupSighting.get_sighting_guid)
    detection_start_time = base_fields.Function(
        AssetGroupSighting.get_detection_start_time
    )
    curation_start_time = base_fields.Function(AssetGroupSighting.get_curation_start_time)

    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)

    jobs = base_fields.Function(AssetGroupSighting.get_detailed_jobs_json)

    class Meta(BaseAssetGroupSightingSchema.Meta):

        fields = BaseAssetGroupSightingSchema.Meta.fields + (
            AssetGroupSighting.stage.key,
            AssetGroupSighting.config.key,
            'assets',
            'completion',
            'creator',
            'sighting_guid',
            'detection_start_time',
            'curation_start_time',
            'jobs',
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
    individual = base_fields.Dict(default={})
    owner = base_fields.Dict()
    sex = base_fields.String(default=None, allow_none=True)
    submitter = base_fields.Dict(default=None)
    taxonomy = base_fields.UUID()
    time = base_fields.String(default=None)
    timeSpecificity = base_fields.String(default=None)
    updatedHouston = base_fields.DateTime()
    version = base_fields.String(default=None)


class AssetGroupSightingAsSightingSchema(ModelSchema):
    """
    In order for the frontend to render an AGS with the same code that renders a
    sighting, we have to pop out all the fields in AGS.config into the top-level
    of the schema. This is done with AssetGroupSighting.config_field_getter,
    which creates a getter for a config field of a given name. We can add more
    fields using the pattern below.
    """

    createdHouston = base_fields.DateTime(attribute='created')
    updatedHouston = base_fields.DateTime(attribute='updated')
    completion = base_fields.Function(AssetGroupSighting.get_completion)
    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)
    detection_start_time = base_fields.Function(
        AssetGroupSighting.get_detection_start_time
    )
    curation_start_time = base_fields.Function(AssetGroupSighting.get_curation_start_time)

    # Note: these config_field_getter vars should conform to SIGHTING_FIELDS_IN_AGS_CONFIG
    # at the top of this file
    time = base_fields.Function(AssetGroupSighting.config_field_getter('time'))
    timeSpecificity = base_fields.Function(
        AssetGroupSighting.config_field_getter('timeSpecificity')
    )
    encounters = base_fields.Nested(
        AssetGroupSightingEncounterSchema,
        attribute='get_encounters_json',
        many=True,
    )

    assets = base_fields.Nested(
        ExtendedAssetDetailedAnnotationsSchema,
        attribute='get_assets',
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
    verbatimEventDate = base_fields.Function(
        AssetGroupSighting.config_field_getter('verbatimEventDate', default='')
    )
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
    speciesDetectionModel = base_fields.Function(
        AssetGroupSighting.config_field_getter('speciesDetectionModel', default=[])
    )

    # These are fields that are in Sighting but don't exist for
    # AssetGroupSighting
    createdEDM = base_fields.DateTime(default=None)
    customFields = base_fields.Dict(attribute='get_custom_fields')
    version = base_fields.String(default=None)
    identification_start_time = base_fields.String(default=None)
    unreviewed_start_time = base_fields.String(default=None)
    review_time = base_fields.String(default=None)

    hasView = base_fields.Boolean(default=True)
    hasEdit = base_fields.Boolean(default=True)

    class Meta:
        # adds extras to the fields already defined above
        additional = (
            AssetGroupSighting.guid.key,
            AssetGroupSighting.created.key,
            AssetGroupSighting.updated.key,
            AssetGroupSighting.stage.key,
            AssetGroupSighting.asset_group_guid.key,
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
        'DetailedAssetGroupSightingSchema',
        many=True,
    )

    class Meta(CreateAssetGroupSchema.Meta):
        fields = CreateAssetGroupSchema.Meta.fields + ('assets', 'asset_group_sightings')
        dump_only = CreateAssetGroupSchema.Meta.dump_only


class DebugAssetGroupSightingSchema(DetailedAssetGroupSightingSchema):
    jobs = base_fields.Function(AssetGroupSighting.get_debug_jobs_json)


class DebugAssetGroupSchema(CreateAssetGroupSchema):
    """
    Debug Asset_group schema exposes all fields as a debug util.
    """

    assets = base_fields.Nested(
        'DetailedAssetSchema',
        many=True,
    )
    asset_group_sightings = base_fields.Nested(
        DebugAssetGroupSightingSchema,
        many=True,
    )

    class Meta(CreateAssetGroupSchema.Meta):
        fields = CreateAssetGroupSchema.Meta.fields + (
            AssetGroup.config.key,
            'assets',
            'asset_group_sightings',
        )
        dump_only = CreateAssetGroupSchema.Meta.dump_only
