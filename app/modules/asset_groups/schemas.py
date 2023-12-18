# -*- coding: utf-8 -*-
"""
Serialization schemas for Asset_groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields

from app.extensions.git_store.schemas import (
    BaseGitStoreSchema,
    CreateGitStoreSchema,
    DetailedGitStoreSchema,
)
from app.modules.assets.schemas import ExtendedAssetDetailedAnnotationsSchema
from flask_restx_patched import ModelSchema

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
    'encounterCounts',
    'id',
    'comments',
    'featuredAssetGuid',
}


class BaseAssetGroupSchema(BaseGitStoreSchema):
    """
    Base Asset_group schema exposes only the most general fields.
    """

    pass


class CreateAssetGroupSchema(CreateGitStoreSchema):
    """
    Detailed Asset_group schema exposes all useful fields.
    """

    pass


class DetailedAssetGroupSchema(DetailedGitStoreSchema):
    """
    Detailed Asset_group schema exposes all useful fields.
    """

    asset_group_sightings = base_fields.Nested(
        'DetailedAssetGroupSightingSchema',
        many=True,
    )

    progress_preparation = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    progress_detection = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    progress_identification = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    pipeline_status = base_fields.Function(lambda ag: ag.get_pipeline_status())

    class Meta(DetailedGitStoreSchema.Meta):
        fields = DetailedGitStoreSchema.Meta.fields + (
            'asset_group_sightings',
            'progress_preparation',
            'progress_detection',
            'progress_identification',
            'pipeline_status',
        )
        dump_only = DetailedGitStoreSchema.Meta.dump_only


class BaseAssetGroupSightingSchema(ModelSchema):
    """
    Asset_group sighting schema
    """

    time = base_fields.Function(AssetGroupSighting.config_field_getter('time'))
    timeSpecificity = base_fields.Function(
        AssetGroupSighting.config_field_getter('timeSpecificity')
    )
    locationId = base_fields.Function(
        AssetGroupSighting.config_field_getter('locationId')
    )
    submissionTime = base_fields.Function(lambda ags: ags.get_submission_time_isoformat())
    numAnnotations = base_fields.Function(lambda ags: ags.num_annotations())
    numEncounters = base_fields.Function(lambda ags: ags.num_encounters())

    class Meta:
        # pylint: disable=missing-docstring
        model = AssetGroupSighting
        fields = (
            AssetGroupSighting.guid.key,
            AssetGroupSighting.stage.key,
            'elasticsearchable',
            AssetGroupSighting.indexed.key,
            'time',
            'timeSpecificity',
            'locationId',
            'submissionTime',
            'numberAnnotations',
            'numberEncounters',
        )
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

    sighting_guid = base_fields.Function(lambda ags: ags.get_sighting_guid())
    detection_start_time = base_fields.Function(
        lambda ags: ags.get_detection_start_time()
    )
    curation_start_time = base_fields.Function(lambda ags: ags.get_curation_start_time())

    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)

    jobs = base_fields.Function(lambda ags: ags.get_detailed_jobs_json())

    progress_preparation = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    progress_detection = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    progress_identification = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    class Meta(BaseAssetGroupSightingSchema.Meta):

        fields = BaseAssetGroupSightingSchema.Meta.fields + (
            AssetGroupSighting.config.key,
            'assets',
            'creator',
            'sighting_guid',
            'detection_start_time',
            'curation_start_time',
            'jobs',
            AssetGroupSighting.asset_group_guid.key,
            'progress_preparation',
            'progress_detection',
            'progress_identification',
        )
        dump_only = BaseAssetGroupSightingSchema.Meta.dump_only + (
            AssetGroupSighting.jobs.key,
        )


class AssetGroupSightingEncounterSchema(ModelSchema):

    created = base_fields.DateTime()
    createdHouston = base_fields.DateTime()
    customFields = base_fields.Dict(default={})
    decimalLatitude = base_fields.Float(default=None)
    decimalLongitude = base_fields.Float(default=None)
    guid = base_fields.UUID()
    hasEdit = base_fields.Boolean(default=False)
    hasView = base_fields.Boolean(default=False)
    individual = base_fields.Dict(default={})
    owner = base_fields.Dict()
    sex = base_fields.String(default=None, allow_none=True)
    submitter = base_fields.Dict(default=None)
    taxonomy = base_fields.UUID()
    time = base_fields.String(default=None)
    timeSpecificity = base_fields.String(default=None)
    updated = base_fields.DateTime()
    version = base_fields.String(default=None)
    annotations = base_fields.Dict()
    locationId = base_fields.String(default=None)
    verbatimLocality = base_fields.String(default=None)


class AssetGroupSightingAsSightingSchema(ModelSchema):
    """
    In order for the frontend to render an AGS with the same code that renders a
    sighting, we have to pop out all the fields in AGS.config into the top-level
    of the schema. This is done with AssetGroupSighting.config_field_getter,
    which creates a getter for a config field of a given name. We can add more
    fields using the pattern below.
    """

    created = base_fields.DateTime(attribute='created')
    updated = base_fields.DateTime(attribute='updated')
    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)
    detection_start_time = base_fields.Function(
        lambda ags: ags.get_detection_start_time()
    )
    curation_start_time = base_fields.Function(lambda ags: ags.get_curation_start_time())

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
    customFields = base_fields.Dict(attribute='get_custom_fields')
    version = base_fields.String(default=None)
    identification_start_time = base_fields.String(default=None)
    unreviewed_start_time = base_fields.String(default=None)
    review_time = base_fields.String(default=None)
    submissionTime = base_fields.Function(lambda ags: ags.get_submission_time_isoformat())

    hasEdit = base_fields.Function(lambda ags: ags.current_user_has_edit_permission())
    hasView = base_fields.Function(lambda ags: ags.current_user_has_view_permission())

    progress_preparation = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    progress_detection = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    progress_identification = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    class Meta:
        # adds extras to the fields already defined above
        additional = (
            AssetGroupSighting.guid.key,
            AssetGroupSighting.created.key,
            AssetGroupSighting.updated.key,
            AssetGroupSighting.stage.key,
            AssetGroupSighting.asset_group_guid.key,
            'progress_preparation',
            'progress_detection',
            'progress_identification',
        )
        dump_only = BaseAssetGroupSightingSchema.Meta.dump_only


class AssetGroupSightingAsSightingWithPipelineStatusSchema(
    AssetGroupSightingAsSightingSchema
):
    pipeline_status = base_fields.Function(lambda ags: ags.get_pipeline_status())


class DebugAssetGroupSightingSchema(DetailedAssetGroupSightingSchema):
    detection_attempts = base_fields.Function(lambda ags: ags.detection_attempts())
    jobs = base_fields.Function(lambda ags: ags.get_debug_jobs_json())


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
