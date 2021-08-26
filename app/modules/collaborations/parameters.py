# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Collaborations resources RESTful API
-----------------------------------------------------------
"""

from flask_restx_patched import Parameters, PatchJSONParameters
from flask_marshmallow import base_fields

from . import schemas
from flask_login import current_user
from app.modules.users.permissions.types import AccessOperation
from app.modules.users.permissions import rules


class CreateCollaborationParameters(Parameters, schemas.DetailedCollaborationSchema):
    user_guid = base_fields.UUID(
        description='The GUID of the other user',
        required=True,
    )
    # This is used for when a user manager is creating a collaboration between two different users.
    second_user_guid = base_fields.UUID(
        description='The GUID of the second user',
        required=False,
    )

    class Meta(schemas.DetailedCollaborationSchema.Meta):
        pass


class PatchCollaborationDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
    )

    PATH_CHOICES = (
        '/view_permission',
        '/edit_permission',
    )

    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False

        has_permission = rules.ObjectActionRule(obj, AccessOperation.WRITE).check()

        if has_permission:
            if field == 'view_permission':
                ret_val = obj.set_read_approval_state_for_user(current_user.guid, value)
            if field == 'edit_permission':
                ret_val = obj.set_edit_approval_state_for_user(current_user.guid, value)
        return ret_val
