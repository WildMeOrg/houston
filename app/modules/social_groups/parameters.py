# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Social Groups resources RESTful API
-----------------------------------------------------------
"""
import logging

from flask_marshmallow import base_fields

import app.extensions.logging as AuditLog
from flask_restx_patched import Parameters, PatchJSONParameters

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

    PATH_CHOICES = ('/name', '/members')

    @classmethod
    def add(cls, obj, field, value, state):
        if field == 'members':
            from . import resources

            members = {
                str(member.individual_guid): {'roles': member.roles}
                for member in obj.members
            }
            for member_guid, roles in value.items():
                members[member_guid] = roles

            resources.validate_members(members)

            for member_guid, roles in value.items():
                obj.remove_member(member_guid)
                obj.add_member(member_guid, roles)
            return True
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        ret_val = False
        if field == 'name':
            obj.name = value
            ret_val = True
        # Complete replacement of all members
        elif field == 'members':
            from . import resources

            resources.validate_members(value)

            # remove all that were there
            obj.remove_all_members()

            for member_guid in value:
                obj.add_member(member_guid, value[member_guid])
            ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        # Any researcher can remove a member in the group
        ret_val = False
        if field == 'members':
            if isinstance(value, list):
                members = value
            else:
                members = [value]
            for member in members:
                ret_val = obj.remove_member(member)
            msg = f'Removing members {members}'
            AuditLog.audit_log_object(log, obj, msg)
        return ret_val
