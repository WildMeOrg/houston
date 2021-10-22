# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Social Groups resources RESTful API
-----------------------------------------------------------
"""
import logging
from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters
from app.utils import HoustonException

from . import schemas

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SocialGroupMembers(Parameters, schemas.SocialGroupMemberSchema):
    class Meta(schemas.SocialGroupMemberSchema.Meta):
        pass


class CreateSocialGroupParameters(Parameters, schemas.DetailedSocialGroupSchema):
    name = base_fields.String(description='The name of the social group', required=True)
    members = base_fields.Nested(SocialGroupMembers, required=True)

    class Meta(schemas.DetailedSocialGroupSchema.Meta):
        pass


class PatchSocialGroupDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES = ('/name', '/members', '/member')

    @classmethod
    def add(cls, obj, field, value, state):
        # For all fields, Add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        ret_val = False
        if field == 'name':
            obj.name = value
            ret_val = True
        # replacement of individual member, this is how roles are updated
        elif field == 'member':
            if not isinstance(value, dict):
                raise HoustonException(log, 'value for a member must be a dictionary')
            if not (set(value.keys()) == set({'guid', 'roles'})):
                raise HoustonException(
                    log, 'value for a member must contain guid and roles as keys'
                )
            current_roles = {}
            for member in obj.members:
                if str(member.individual_guid) != value['guid']:
                    for role in member.roles:
                        current_roles[role] = True
            from . import resources

            resources.validate_member(value['guid'], value, current_roles)

            # Just remove and replace, allows add and replace to be virtually identical
            if obj.get_member(value['guid']):
                obj.remove_member(value['guid'])
            obj.add_member(value['guid'], value)
            ret_val = True
        # Complete replacement of all members
        elif field == 'members':
            from . import resources

            resources.validate_members(value)
            # remove all that were there
            for current_member in obj.members:
                obj.remove_member(str(current_member.individual_guid))

            for member_guid in value:
                obj.add_member(member_guid, value[member_guid])
            ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        # TODO any researcher can remove a member in the group, they don't need view permission as they do for an add
        # Do we care about this?
        ret_val = False
        if field == 'member':
            ret_val = obj.remove_member(value)
        return ret_val
