# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Collaborations resources RESTful API
-----------------------------------------------------------
"""
import logging

from flask_login import current_user
from flask_marshmallow import base_fields

from app.modules.users.permissions import rules
from app.modules.users.permissions.types import AccessOperation
from app.utils import HoustonException
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


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
        '/managed_view_permission',
        '/managed_edit_permission',
    )

    @classmethod
    def get_managed_values(cls, field, value):
        if not isinstance(value, dict):
            raise HoustonException(
                log, f'Value for {field} must be passed as a dictionary'
            )

        if 'user_guid' not in value.keys():
            raise HoustonException(log, f'Value for {field} must contain a user_guid')

        if 'permission' not in value.keys():
            raise HoustonException(
                log, f'Value for {field} must contain a permission field'
            )

        # Is the user guid valid?
        from app.modules.users.models import User

        user = User.query.get(value['user_guid'])
        if not user:
            raise HoustonException(log, f"User for {value['user_guid']} not found")

        return user.guid, value['permission']

    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False

        if field == 'view_permission':
            if rules.ObjectActionRule(obj, AccessOperation.WRITE).check():
                ret_val = obj.set_read_approval_state_for_user(current_user.guid, value)

        elif field == 'edit_permission':
            if rules.ObjectActionRule(obj, AccessOperation.WRITE).check():
                ret_val = obj.set_edit_approval_state_for_user(current_user.guid, value)

        elif field == 'managed_view_permission':
            if current_user.is_user_manager:
                user_guid, permission = cls.get_managed_values(field, value)
                ret_val = obj.set_read_approval_state_for_user(user_guid, permission)

        elif field == 'managed_edit_permission':
            if current_user.is_user_manager:
                user_guid, permission = cls.get_managed_values(field, value)
                ret_val = obj.set_edit_approval_state_for_user(user_guid, permission)

        return ret_val
