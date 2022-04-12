# -*- coding: utf-8 -*-
"""
Serialization schemas for Relationships resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import Relationship
from .models import RelationshipIndividualMember


class BaseRelationshipSchema(ModelSchema):
    """
    Base Relationship schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = Relationship
        fields = (
            Relationship.guid.key,
            'elasticsearchable',
            Relationship.indexed.key,
        )
        dump_only = (Relationship.guid.key,)


class BaseRelationshipIndividualMemberSchema(ModelSchema):
    """
    BaseRelationshipIndividualMemberSchema exposes useful fields about a relationships members..
    """

    individual_role_label = base_fields.String()

    class Meta:
        # pylint: disable=missing-docstring
        model = RelationshipIndividualMember
        fields = (
            RelationshipIndividualMember.individual_role_guid.key,
            'individual_role_label',
            RelationshipIndividualMember.individual_guid.key,
        )
        dump_only = (
            RelationshipIndividualMember.individual_role_guid.key,
            'individual_role_label',
            RelationshipIndividualMember.individual_guid.key,
        )


class DetailedRelationshipSchema(BaseRelationshipSchema):
    """
    Detailed Relationship schema exposes all useful fields.
    """

    individual_members = base_fields.Nested(
        'BaseRelationshipIndividualMemberSchema',
        many=True,
        only=('guid', 'individual_guid', 'individual_role_label', 'individual_role_guid'),
    )

    class Meta(BaseRelationshipSchema.Meta):
        fields = BaseRelationshipSchema.Meta.fields + (
            Relationship.created.key,
            Relationship.updated.key,
            Relationship.start_date.key,
            Relationship.end_date.key,
            Relationship.type_guid.key,
            'type_label',
            'individual_members',
        )
        dump_only = BaseRelationshipSchema.Meta.dump_only + (
            Relationship.created.key,
            Relationship.updated.key,
            Relationship.start_date.key,
            Relationship.end_date.key,
            Relationship.type_guid.key,
            'type_label',
            'individual_members',
        )
