# -*- coding: utf-8 -*-
"""
Serialization schemas for Encounters resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import Encounter


class BaseEncounterSchema(ModelSchema):
    """
    Base Encounter schema exposes only the most general fields.
    """

    annotations = base_fields.Nested('BaseAnnotationSchema', many=True)
    submitter = base_fields.Nested('PublicUserSchema', many=False)
    owner = base_fields.Nested('PublicUserSchema', many=False)
    hasView = base_fields.Function(Encounter.current_user_has_view_permission)
    hasEdit = base_fields.Function(Encounter.current_user_has_edit_permission)

    class Meta:
        # pylint: disable=missing-docstring
        model = Encounter
        fields = (Encounter.guid.key,)
        dump_only = (Encounter.guid.key,)


class DetailedEncounterSchema(BaseEncounterSchema):
    """
    Detailed Encounter schema exposes all useful fields.
    """

    class Meta(BaseEncounterSchema.Meta):
        fields = BaseEncounterSchema.Meta.fields + (
            Encounter.created.key,
            Encounter.updated.key,
            Encounter.owner_guid.key,
            Encounter.public.key,
            Encounter.annotations.key,
            Encounter.owner.key,
            Encounter.submitter.key,
        )
        dump_only = BaseEncounterSchema.Meta.dump_only + (
            Encounter.created.key,
            Encounter.updated.key,
        )


class AugmentedEdmEncounterSchema(BaseEncounterSchema):
    annotations = base_fields.Nested(
        'BaseAnnotationSchema', many=True, only=('guid', 'asset_guid', 'ia_class')
    )

    createdHouston = base_fields.DateTime(attribute='created')
    updatedHouston = base_fields.DateTime(attribute='updated')

    class Meta(BaseEncounterSchema.Meta):
        fields = BaseEncounterSchema.Meta.fields + (
            'createdHouston',
            'updatedHouston',
            Encounter.owner.key,
            Encounter.submitter.key,
            'hasView',
            'hasEdit',
            'annotations',
        )


class AugmentedIndividualApiEncounterSchema(BaseEncounterSchema):

    submitter = base_fields.Nested('BaseUserSchema', many=False, exclude='email')
    owner = base_fields.Nested('BaseUserSchema', many=False, exclude='email')

    class Meta(BaseEncounterSchema.Meta):
        fields = BaseEncounterSchema.Meta.fields + (
            Encounter.sighting.key,
            'submitter',
            'owner',
            'hasView',
            'hasEdit',
            'asset_group_sighting_encounter_guid'
        )

