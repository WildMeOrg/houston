# -*- coding: utf-8 -*-
"""
Serialization schemas for Sightings resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from .models import Sighting


class BaseSightingSchema(ModelSchema):
    """
    Base Sighting schema exposes only the most general fields.
    """

    hasView = base_fields.Function(Sighting.current_user_has_view_permission)
    hasEdit = base_fields.Function(Sighting.current_user_has_edit_permission)
    time = base_fields.Function(Sighting.get_time_isoformat_in_timezone)
    timeSpecificity = base_fields.Function(Sighting.get_time_specificity)

    class Meta:
        # pylint: disable=missing-docstring
        model = Sighting
        fields = (Sighting.guid.key,)
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


class TimedSightingSchema(CreateSightingSchema):
    """
    Timed Sighting schema adds the stage times
    """

    detection_start_time = base_fields.Function(Sighting.get_detection_start_time)
    curation_start_time = base_fields.Function(Sighting.get_curation_start_time)
    identification_start_time = base_fields.Function(
        Sighting.get_identification_start_time
    )
    unreviewed_start_time = base_fields.Function(Sighting.get_unreviewed_start_time)
    review_time = base_fields.Function(Sighting.get_review_time)

    class Meta(CreateSightingSchema.Meta):
        fields = CreateSightingSchema.Meta.fields + (
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


class AugmentedEdmSightingSchema(TimedSightingSchema):
    """
    Sighting schema with EDM and Houston data.
    """

    createdHouston = base_fields.DateTime(attribute='created')
    updatedHouston = base_fields.DateTime(attribute='updated')
    assets = base_fields.Nested(
        'ExtendedAssetSchema',
        attribute='get_assets',
        many=True,
    )
    featuredAssetGuid = base_fields.UUID(attribute='featured_asset_guid')
    creator = base_fields.Nested('PublicUserSchema', attribute='get_owner', many=False)
    speciesDetectionModel = base_fields.Function(
        Sighting.config_field_getter('speciesDetectionModel', default=[])
    )

    class Meta(TimedSightingSchema.Meta):
        """
        Desired Sighting fields.
        """

        fields = TimedSightingSchema.Meta.fields + (
            'createdHouston',
            'updatedHouston',
            'hasView',
            'hasEdit',
            'assets',
            'featuredAssetGuid',
            'stage',
            'creator',
            'time',
            'timeSpecificity',
            'speciesDetectionModel',
        )


class DetailedSightingJobSchema(ModelSchema):
    job_id = base_fields.String()
    matching_set = base_fields.String()
    active = base_fields.Boolean()
    start = base_fields.DateTime()
    algorithm = base_fields.String()
    annotation = base_fields.String()


class DebugSightingSchema(AugmentedEdmSightingSchema):
    assets = base_fields.Nested(
        'DetailedAssetSchema',
        attribute='get_assets',
        many=True,
    )
    jobs = base_fields.Function(Sighting.get_jobs_json)

    class Meta(AugmentedEdmSightingSchema.Meta):
        fields = AugmentedEdmSightingSchema.Meta.fields + ('jobs',)
