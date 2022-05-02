# -*- coding: utf-8 -*-
"""
Serialization schemas for Individuals resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema
from flask_marshmallow import base_fields

from .models import Individual

from app.modules.names.schemas import DetailedNameSchema
from app.modules.encounters.schemas import (
    DetailedEncounterSchema,
    ElasticsearchEncounterSchema,
)
from app.modules.relationships.schemas import (
    DetailedRelationshipSchema,
    BaseRelationshipIndividualMemberSchema,
)


class BaseIndividualSchema(ModelSchema):
    """
    Base Individual schema exposes only the most general fields.
    """

    hasView = base_fields.Function(Individual.current_user_has_view_permission)
    hasEdit = base_fields.Function(Individual.current_user_has_edit_permission)

    class Meta:
        # pylint: disable=missing-docstring
        model = Individual
        fields = (
            Individual.guid.key,
            'hasView',
            'hasEdit',
            'elasticsearchable',
            Individual.indexed.key,
        )
        dump_only = (Individual.guid.key,)


class NamedIndividualSchema(BaseIndividualSchema):
    """
    Detailed Individual schema exposes all useful fields.
    """

    names = base_fields.Nested(
        DetailedNameSchema,
        attribute='names',
        many=True,
    )

    class Meta(BaseIndividualSchema.Meta):
        fields = BaseIndividualSchema.Meta.fields + ('names',)


class IndividualRelationshipSchema(DetailedRelationshipSchema):
    """
    Relationship schema used in the individual API
    """

    class RelationshipIndividualMemberSchema(BaseRelationshipIndividualMemberSchema):
        individual_first_name = base_fields.String()

        class Meta(BaseRelationshipIndividualMemberSchema.Meta):
            fields = BaseRelationshipIndividualMemberSchema.Meta.fields + (
                'individual_first_name',
            )
            dump_only = BaseRelationshipIndividualMemberSchema.Meta.dump_only + (
                'individual_first_name',
            )

    individual_members = base_fields.Nested(
        RelationshipIndividualMemberSchema,
        many=True,
        only=(
            'guid',
            'individual_guid',
            'individual_role_label',
            'individual_role_guid',
            'individual_first_name',
        ),
    )

    class Meta(DetailedRelationshipSchema.Meta):
        fields = (
            'guid',
            'type_label',
            'type_guid',
            'individual_members',
        )


class DetailedIndividualSchema(NamedIndividualSchema):
    """
    Detailed Individual schema exposes all useful fields.
    """

    featuredAssetGuid = base_fields.Function(Individual.get_featured_asset_guid)
    social_groups = base_fields.Function(Individual.get_social_groups_json)
    relationships = base_fields.Nested(IndividualRelationshipSchema, many=True)

    class Meta(NamedIndividualSchema.Meta):
        fields = NamedIndividualSchema.Meta.fields + (
            Individual.created.key,
            Individual.updated.key,
            'featuredAssetGuid',
            'social_groups',
            'relationships',
        )
        dump_only = NamedIndividualSchema.Meta.dump_only + (
            Individual.created.key,
            Individual.updated.key,
            'relationships',
        )


class ElasticsearchIndividualSchema(ModelSchema):
    """
    Base Individual schema exposes only the most general fields.
    """

    featuredAssetGuid = base_fields.Function(Individual.get_featured_asset_guid)
    names = base_fields.Function(Individual.get_name_values)
    firstName = base_fields.Function(Individual.get_first_name)
    adoptionName = base_fields.Function(Individual.get_adoption_name)
    encounters = base_fields.Nested(ElasticsearchEncounterSchema, many=True)
    social_groups = base_fields.Function(Individual.get_social_groups_json)
    sex = base_fields.Function(Individual.get_sex)
    birth = base_fields.Function(Individual.get_time_of_birth)
    death = base_fields.Function(Individual.get_time_of_death)
    comments = base_fields.Function(Individual.get_comments)
    customFields = base_fields.Function(Individual.get_custom_fields)
    taxonomy_guid = base_fields.Function(Individual.get_taxonomy_guid_inherit_encounters)
    has_annotations = base_fields.Function(Individual.has_annotations)
    last_seen = base_fields.Function(Individual.get_last_seen_time)
    taxonomy_names = base_fields.Function(Individual.get_taxonomy_names)

    class Meta:
        # pylint: disable=missing-docstring
        model = Individual
        fields = (
            Individual.guid.key,
            'elasticsearchable',
            Individual.indexed.key,
            Individual.created.key,
            Individual.updated.key,
            'featuredAssetGuid',
            'names',
            'firstName',
            'adoptionName',
            'taxonomy_guid',
            'social_groups',
            'sex',
            'encounters',
            'birth',
            'death',
            'comments',
            'customFields',
            'has_annotations',
            'last_seen',
            'taxonomy_names',
        )
        dump_only = (
            Individual.guid.key,
            Individual.created.key,
            Individual.updated.key,
        )


class DebugIndividualSchema(DetailedIndividualSchema):
    """
    Debug Individual schema exposes all fields.
    """

    houston_encounters = base_fields.Nested(
        DetailedEncounterSchema,
        attribute='encounters',
        many=True,
    )

    class Meta(DetailedIndividualSchema.Meta):
        fields = DetailedIndividualSchema.Meta.fields + ('houston_encounters',)
