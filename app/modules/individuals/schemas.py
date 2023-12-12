# -*- coding: utf-8 -*-
"""
Serialization schemas for Individuals resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields

from app.modules.encounters.schemas import (
    DetailedEncounterSchema,
    ElasticsearchEncounterSchema,
)
from app.modules.names.schemas import DetailedNameSchema
from app.modules.relationships.schemas import (
    BaseRelationshipIndividualMemberSchema,
    DetailedRelationshipSchema,
)
from flask_restx_patched import ModelSchema

from .models import Individual


class BaseIndividualSchema(ModelSchema):
    """
    Base Individual schema exposes only the most general fields.
    """

    hasView = base_fields.Function(lambda ind: ind.current_user_has_view_permission())
    hasEdit = base_fields.Function(lambda ind: ind.current_user_has_edit_permission())

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


class CreateIndividualSchema(BaseIndividualSchema):
    """
    Create Individual schema for just the fields needed at creation
    """

    class Meta(BaseIndividualSchema.Meta):
        fields = BaseIndividualSchema.Meta.fields + (
            Individual.created.key,
            Individual.updated.key,
            Individual.sex.key,
        )
        dump_only = BaseIndividualSchema.Meta.dump_only + (
            Individual.created.key,
            Individual.updated.key,
        )


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


class BasicNamedIndividualSchema(ModelSchema):
    """
    Detailed Individual schema exposes all useful fields.
    """

    names = base_fields.Function(lambda ind: ind.get_name_values())
    id = base_fields.Function(lambda ind: ind.guid)

    class Meta:
        model = Individual
        fields = (
            'id',
            'names',
        )


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

    featuredAssetGuid = base_fields.Function(lambda ind: ind.get_featured_asset_guid())
    social_groups = base_fields.Function(lambda ind: ind.get_social_groups_json())
    relationships = base_fields.Nested(IndividualRelationshipSchema, many=True)
    customFields = base_fields.Function(lambda ind: ind.get_custom_fields())
    encounters = base_fields.Nested(
        DetailedEncounterSchema,
        attribute='encounters',
        many=True,
    )
    sex = base_fields.Function(lambda ind: ind.get_sex())
    taxonomy = base_fields.Function(lambda ind: ind.get_taxonomy_guid())
    timeOfBirth = base_fields.DateTime(attribute='time_of_birth')
    timeOfDeath = base_fields.DateTime(attribute='time_of_death')

    class Meta(NamedIndividualSchema.Meta):
        fields = NamedIndividualSchema.Meta.fields + (
            Individual.created.key,
            Individual.updated.key,
            'featuredAssetGuid',
            'social_groups',
            'relationships',
            Individual.comments.key,
            'customFields',
            'timeOfBirth',
            'timeOfDeath',
            'sex',
            'taxonomy',
            'encounters',
        )
        dump_only = NamedIndividualSchema.Meta.dump_only + (
            Individual.created.key,
            Individual.updated.key,
            'relationships',
        )


class ElasticsearchIndividualSchema(ModelSchema):
    """
    ElasticsearchIndividualSchema is used for indexing individuals for ES
    """

    featuredAssetGuid = base_fields.Function(lambda ind: ind.get_featured_asset_guid())
    names = base_fields.Function(lambda ind: ind.get_name_values())
    namesWithContexts = base_fields.Function(lambda ind: ind.get_names_with_contexts())
    firstName = base_fields.Function(lambda ind: ind.get_first_name())
    firstName_keyword = base_fields.Function(lambda ind: ind.get_first_name_keyword())
    adoptionName = base_fields.Function(lambda ind: ind.get_adoption_name())
    encounters = base_fields.Nested(ElasticsearchEncounterSchema, many=True)
    social_groups = base_fields.Function(
        lambda ind: ind.get_social_groups_elasticsearch()
    )
    relationships = base_fields.Function(
        lambda ind: ind.get_relationships_elasticsearch()
    )
    sex = base_fields.Function(lambda ind: ind.get_sex())
    birth = base_fields.Function(lambda ind: ind.get_time_of_birth())
    death = base_fields.Function(lambda ind: ind.get_time_of_death())
    comments = base_fields.Function(lambda ind: ind.get_comments())
    customFields = base_fields.Function(lambda ind: ind.get_custom_fields_elasticsearch())
    taxonomy_guid = base_fields.Function(lambda ind: ind.get_taxonomy_guid())
    has_annotations = base_fields.Function(lambda ind: ind.has_annotations())
    num_encounters = base_fields.Function(lambda ind: ind.num_encounters())
    last_seen = base_fields.Function(lambda ind: ind.get_last_seen_time_isoformat())
    last_seen_specificity = base_fields.Function(
        lambda ind: ind.get_last_seen_time_specificity()
    )
    taxonomy_names = base_fields.Function(
        lambda ind: ind.get_taxonomy_names(inherit_encounters=False)
    )
    numberSightings = base_fields.Function(lambda ind: ind.get_number_sightings())
    viewers = base_fields.Function(lambda ind: ind.viewer_guids())

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
            'namesWithContexts',
            'firstName',
            'firstName_keyword',
            'adoptionName',
            'taxonomy_guid',
            'social_groups',
            'relationships',
            'sex',
            'encounters',
            'birth',
            'death',
            'comments',
            'customFields',
            'has_annotations',
            'num_encounters',
            'last_seen',
            'last_seen_specificity',
            'taxonomy_names',
            'numberSightings',
            'viewers',
        )
        dump_only = (
            Individual.guid.key,
            Individual.created.key,
            Individual.updated.key,
        )


class ElasticsearchIndividualReturnSchema(ModelSchema):
    """
    ElasticsearchIndividualSchema is used for showing results to the user upon return.
    """

    hasView = base_fields.Function(lambda ind: ind.current_user_has_view_permission())
    featuredAssetGuid = base_fields.Function(lambda ind: ind.get_featured_asset_guid())
    names = base_fields.Function(lambda ind: ind.get_name_values())
    firstName = base_fields.Function(lambda ind: ind.get_first_name())
    firstName_keyword = base_fields.Function(lambda ind: ind.get_first_name_keyword())
    adoptionName = base_fields.Function(lambda ind: ind.get_adoption_name())
    social_groups = base_fields.Function(lambda ind: ind.get_social_groups_json())
    sex = base_fields.Function(lambda ind: ind.get_sex())
    birth = base_fields.Function(lambda ind: ind.get_time_of_birth())
    death = base_fields.Function(lambda ind: ind.get_time_of_death())
    comments = base_fields.Function(lambda ind: ind.get_comments())
    customFields = base_fields.Function(lambda ind: ind.get_custom_fields())
    taxonomy_guid = base_fields.Function(
        lambda ind: ind.get_taxonomy_guid_inherit_encounters()
    )
    has_annotations = base_fields.Function(lambda ind: ind.has_annotations())
    last_seen = base_fields.Function(lambda ind: ind.get_last_seen_time_isoformat())
    last_seen_specificity = base_fields.Function(
        lambda ind: ind.get_last_seen_time_specificity(),
    )
    last_seen_verbatimLocality = base_fields.Function(
        lambda ind: ind.get_most_recent_verbatim_locality()
    )
    last_seen_location_name = base_fields.Function(
        lambda ind: ind.get_most_recent_location_name()
    )
    taxonomy_names = base_fields.Function(lambda ind: ind.get_taxonomy_names())

    encounters = base_fields.Function(lambda ind: ind.get_encounter_guids())
    num_encounters = base_fields.Function(lambda ind: ind.num_encounters())

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
            'firstName_keyword',
            'adoptionName',
            'taxonomy_guid',
            'social_groups',
            'sex',
            'encounters',
            'num_encounters',
            'birth',
            'death',
            'comments',
            'customFields',
            'has_annotations',
            'last_seen',
            'last_seen_specificity',
            'last_seen_verbatimLocality',
            'last_seen_location_name',
            'taxonomy_names',
            'hasView',
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

    encounters = base_fields.Nested(
        DetailedEncounterSchema,
        attribute='encounters',
        many=True,
    )

    class Meta(DetailedIndividualSchema.Meta):
        fields = DetailedIndividualSchema.Meta.fields + ('encounters',)
