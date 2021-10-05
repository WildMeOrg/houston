# -*- coding: utf-8 -*-
"""
Serialization schemas for Sightings resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from app.modules.assets.schemas import DetailedAssetSchema

from .models import Sighting


class BaseSightingSchema(ModelSchema):
    """
    Base Sighting schema exposes only the most general fields.
    """

    hasView = base_fields.Function(Sighting.current_user_has_view_permission)
    hasEdit = base_fields.Function(Sighting.current_user_has_edit_permission)

    class Meta:
        # pylint: disable=missing-docstring
        model = Sighting
        fields = (Sighting.guid.key,)
        dump_only = (Sighting.guid.key,)


class DetailedSightingSchema(BaseSightingSchema):
    """
    Detailed Sighting schema exposes all useful fields.
    """

    class Meta(BaseSightingSchema.Meta):
        fields = BaseSightingSchema.Meta.fields + (
            Sighting.created.key,
            Sighting.updated.key,
            'hasView',
            'hasEdit',
        )
        dump_only = BaseSightingSchema.Meta.dump_only + (
            Sighting.created.key,
            Sighting.updated.key,
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


class AugmentedEdmSightingSchema(BaseSightingSchema):
    """
    Sighting schema with EDM and Houston data.
    """

    createdHouston = base_fields.DateTime(attribute='created')
    updatedHouston = base_fields.DateTime(attribute='updated')
    assets = base_fields.Nested(
        DetailedAssetSchema,
        attribute='get_assets',
        many=True,
        only=(
            'guid',
            'filename',
            'src',
            'annotations',
            'dimensions',
            'created',
            'updated',
        ),
    )
    featuredAssetGuid = base_fields.UUID(attribute='featured_asset_guid')

    class Meta(BaseSightingSchema.Meta):
        """
        Desired Sighting fields.
        """

        fields = BaseSightingSchema.Meta.fields + (
            'createdHouston',
            'updatedHouston',
            'hasView',
            'hasEdit',
            'assets',
            'featuredAssetGuid',
        )
