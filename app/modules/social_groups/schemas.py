# -*- coding: utf-8 -*-
"""
Serialization schemas for Social Groups resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import SocialGroup, SocialGroupIndividualMembership


class SocialGroupMemberSchema(ModelSchema):
    """
    Data for members in the the SocialGroup
    """

    class Meta:
        model = SocialGroupIndividualMembership
        fields = (SocialGroupIndividualMembership.roles.key,)
        dump_only = (
            SocialGroupIndividualMembership.created.key,
            SocialGroupIndividualMembership.updated.key,
        )


class BaseSocialGroupSchema(ModelSchema):
    """
    Base SocialGroup schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = SocialGroup
        fields = (
            SocialGroup.guid.key,
            SocialGroup.name.key,
            'elasticsearchable',
            SocialGroup.indexed.key,
        )
        dump_only = (SocialGroup.guid.key,)


class DetailedSocialGroupSchema(BaseSocialGroupSchema):
    """
    Detailed SocialGroup schema exposes all useful fields.
    """

    members = base_fields.Function(SocialGroup.get_member_data_as_json)

    class Meta(BaseSocialGroupSchema.Meta):
        fields = BaseSocialGroupSchema.Meta.fields + (
            SocialGroup.created.key,
            SocialGroup.updated.key,
            'members',
        )
        dump_only = BaseSocialGroupSchema.Meta.dump_only + (
            SocialGroup.created.key,
            SocialGroup.updated.key,
            'members',
        )
