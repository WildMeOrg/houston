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
        fields = (Relationship.guid.key,)
        dump_only = (Relationship.guid.key,)


class BaseRelationshipIndividualMemberSchema(ModelSchema):
    """
    BaseRelationshipIndividualMemberSchema exposes useful fields about a relationships members..
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = RelationshipIndividualMember
        fields = (
            RelationshipIndividualMember.individual_role.key,
            RelationshipIndividualMember.individual_guid.key,
        )
        dump_only = (
            RelationshipIndividualMember.individual_role.key,
            RelationshipIndividualMember.individual_guid.key,
        )


class DetailedRelationshipSchema(BaseRelationshipSchema):
    """
    Detailed Relationship schema exposes all useful fields.
    """

    individuals = base_fields.Nested(
        'BaseRelationshipIndividualMemberSchema',
        many=True,
        only=('guid', 'individual_guid', 'individual_role'),
    )

    class Meta(BaseRelationshipSchema.Meta):
        fields = BaseRelationshipSchema.Meta.fields + (
            Relationship.created.key,
            Relationship.updated.key,
            Relationship.start_date.key,
            Relationship.end_date.key,
            Relationship.type.key,
            'individuals',
        )
        dump_only = BaseRelationshipSchema.Meta.dump_only + (
            Relationship.created.key,
            Relationship.updated.key,
            Relationship.start_date.key,
            Relationship.end_date.key,
            Relationship.type.key,
            'individuals',
        )
