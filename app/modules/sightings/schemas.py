# -*- coding: utf-8 -*-
"""
Serialization schemas for Sightings resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields

from app.modules.encounters.schemas import DetailedEncounterSchema
from flask_restx_patched import ModelSchema

from .models import Sighting


class BaseSightingSchema(ModelSchema):
    """
    Base Sighting schema exposes only the most general fields.
    """

    hasView = base_fields.Function(lambda s: s.current_user_has_view_permission())
    hasEdit = base_fields.Function(lambda s: s.current_user_has_edit_permission())
    time = base_fields.Function(lambda s: s.get_time_isoformat_in_timezone())
    timeSpecificity = base_fields.Function(lambda s: s.get_time_specificity())

    class Meta:
        # pylint: disable=missing-docstring
        model = Sighting
        fields = (
            Sighting.guid.key,
            'elasticsearchable',
            Sighting.indexed.key,
        )
        dump_only = (Sighting.guid.key,)


class CreateSightingSchema(BaseSightingSchema):
    """
    Create Sighting schema for all the fields needed at creation
    """

    class Meta(BaseSightingSchema.Meta):
        fields = BaseSightingSchema.Meta.fields + (
            Sighting.created.key,
            Sighting.updated.key,
            'hasView',
            'hasEdit',
            'time',
            'timeSpecificity',
        )
        dump_only = BaseSightingSchema.Meta.dump_only + (
            Sighting.created.key,
            Sighting.updated.key,
        )


class ElasticsearchSightingSchema(BaseSightingSchema):
    """
    Sighting schema for ElasticSearch
    """

    time = base_fields.Function(lambda s: s.get_time_isoformat_in_timezone())
    timeSpecificity = base_fields.Function(lambda s: s.get_time_specificity())
    verbatimLocality = base_fields.String(attribute='verbatim_locality')
    locationId = base_fields.UUID(attribute='location_guid')
    locationId_value = base_fields.Function(lambda s: s.get_location_id_value())
    locationId_keyword = base_fields.Function(lambda s: s.get_location_id_keyword())
    location_geo_point = base_fields.Function(lambda s: s.get_geo_point())
    owners = base_fields.Nested(
        'PublicUserSchema',
        attribute='get_owners',
        many=True,
    )
    taxonomy_guids = base_fields.Function(
        lambda s: s.get_taxonomy_guids_with_encounters()
    )
    customFields = base_fields.Function(lambda s: s.get_custom_fields_elasticsearch())
    submissionTime = base_fields.Function(lambda s: s.get_submission_time_isoformat())
    pipelineState = base_fields.Function(lambda s: s.get_pipeline_state())
    numberEncounters = base_fields.Function(lambda s: s.get_number_encounters())
    encounters = base_fields.Function(lambda s: s.get_encounters_elasticsearch())
    numberImages = base_fields.Function(lambda s: s.get_number_assets())
    numberAnnotations = base_fields.Function(lambda s: s.get_number_annotations())
    # apparently sets do NOT work well, so we need to name-sets to lists here
    individualNames = base_fields.Function(lambda s: list(s.get_individual_names()))
    individualNamesWithContexts = base_fields.Function(
        lambda s: {
            item: list(val)
            for (item, val) in s.get_individual_names_with_contexts().items()
        }
    )

    class Meta:
        # pylint: disable=missing-docstring
        model = Sighting
        fields = (
            Sighting.guid.key,
            'elasticsearchable',
            Sighting.indexed.key,
            Sighting.created.key,
            Sighting.updated.key,
            'time',
            'timeSpecificity',
            'comments',
            'verbatimLocality',
            'locationId',
            'locationId_value',
            'locationId_keyword',
            'location_geo_point',
            'owners',
            'taxonomy_guids',
            'customFields',
            'submissionTime',
            'stage',
            'pipelineState',
            'numberEncounters',
            'encounters',
            'numberImages',
            'numberAnnotations',
            'individualNames',
            'individualNamesWithContexts',
        )
        dump_only = (
            Sighting.guid.key,
            Sighting.created.key,
            Sighting.updated.key,
        )


class TimedSightingSchema(CreateSightingSchema):
    """
    Timed Sighting schema adds the stage times
    """

    detection_start_time = base_fields.Function(lambda s: s.get_detection_start_time())
    curation_start_time = base_fields.Function(lambda s: s.get_curation_start_time())
    identification_start_time = base_fields.Function(
        lambda s: s.get_identification_start_time()
    )
    unreviewed_start_time = base_fields.Function(lambda s: s.get_unreviewed_start_time())
    review_time = base_fields.Function(lambda s: s.get_review_time())

    progress_identification = base_fields.Nested(
        'DetailedProgressSchema',
        many=False,
    )

    class Meta(CreateSightingSchema.Meta):
        fields = CreateSightingSchema.Meta.fields + (
            'progress_identification',
            'detection_start_time',
            'curation_start_time',
            'identification_start_time',
            'unreviewed_start_time',
            'review_time',
        )


class FeaturedAssetOnlySchema(BaseSightingSchema):
    """
    Sighting schema for featured_asset_guid only API.
    """

    class Meta(BaseSightingSchema.Meta):

        fields = BaseSightingSchema.Meta.fields + (Sighting.featured_asset_guid.key,)
        dump_only = BaseSightingSchema.Meta.dump_only + (
            Sighting.featured_asset_guid.key,
        )


class DetailedSightingSchema(TimedSightingSchema):
    """
    Sighting schema with all data.
    """

    created = base_fields.DateTime(attribute='created')
    updated = base_fields.DateTime(attribute='updated')
    assets = base_fields.Nested(
        'DetailedAssetSchema',
        attribute='get_assets',
        many=True,
    )
    featuredAssetGuid = base_fields.Function(lambda s: s.get_featured_asset_guid())
    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)
    speciesDetectionModel = base_fields.Function(
        Sighting.config_field_getter('speciesDetectionModel', default=[])
    )
    jobs = base_fields.Function(lambda s: s.get_jobs_json())
    idConfigs = base_fields.Function(lambda s: s.get_id_configs())
    submissionTime = base_fields.Function(lambda s: s.get_submission_time_isoformat())
    encounters = base_fields.Nested(
        DetailedEncounterSchema,
        attribute='encounters',
        many=True,
    )
    customFields = base_fields.Function(lambda s: s.get_custom_fields())
    decimalLatitude = base_fields.Float(attribute='decimal_latitude')
    decimalLongitude = base_fields.Float(attribute='decimal_longitude')
    verbatimLocality = base_fields.String(attribute='verbatim_locality')
    locationId = base_fields.UUID(attribute='location_guid')
    locationId_value = base_fields.Function(lambda s: s.get_location_id_value())
    locationId_keyword = base_fields.Function(lambda s: s.get_location_id_keyword())
    pipeline_status = base_fields.Function(lambda s: s.get_pipeline_status())
    pipeline_state = base_fields.Function(lambda s: s.get_pipeline_state())

    class Meta(TimedSightingSchema.Meta):
        """
        Desired Sighting fields.
        """

        fields = TimedSightingSchema.Meta.fields + (
            'created',
            'updated',
            'hasView',
            'hasEdit',
            'assets',
            'featuredAssetGuid',
            'stage',
            'match_state',
            'jobs',
            'creator',
            'time',
            'timeSpecificity',
            'speciesDetectionModel',
            'idConfigs',
            'submissionTime',
            'encounters',
            'customFields',
            Sighting.comments.key,
            'decimalLatitude',
            'decimalLongitude',
            'verbatimLocality',
            'locationId_value',
            'locationId',
            'locationId_keyword',
            'pipeline_status',
            'pipeline_state',
        )


class DetailedSightingJobSchema(ModelSchema):
    job_id = base_fields.String()
    matching_set = base_fields.String()
    active = base_fields.Boolean()
    start = base_fields.DateTime()
    algorithm = base_fields.String()
    annotation = base_fields.String()
    end = base_fields.DateTime()
    result = base_fields.Dict()


class DebugSightingSchema(DetailedSightingSchema):
    assets = base_fields.Nested(
        'DetailedAssetSchema',
        attribute='get_assets',
        many=True,
    )
    jobs = base_fields.Function(lambda s: s.get_job_debug())

    class Meta(DetailedSightingSchema.Meta):
        fields = DetailedSightingSchema.Meta.fields + ('jobs',)
