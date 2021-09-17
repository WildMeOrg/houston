# -*- coding: utf-8 -*-
"""
Serialization schemas for Individuals resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from .models import Individual


class BaseIndividualSchema(ModelSchema):
    """
    Base Individual schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Individual
        fields = (Individual.guid.key,)
        dump_only = (Individual.guid.key,)


class DetailedIndividualSchema(BaseIndividualSchema):
    """
    Detailed Individual schema exposes all useful fields.
    """

    hasView = base_fields.Function(Individual.current_user_has_view_permission)
    hasEdit = base_fields.Function(Individual.current_user_has_edit_permission)
    featuredAssetGuid = base_fields.Function(Individual.get_featured_asset_guid)
    encounters = base_fields.Nested('AugmentedIndividualApiEncounterSchema', many=True)

    class Meta(BaseIndividualSchema.Meta):
        fields = BaseIndividualSchema.Meta.fields + (
            Individual.created.key,
            Individual.updated.key,
            'featuredAssetGuid',
            'hasView',
            'hasEdit',
            'encounters'
        )
        dump_only = BaseIndividualSchema.Meta.dump_only + (
            Individual.created.key,
            Individual.updated.key,
            'encounters',
        )
