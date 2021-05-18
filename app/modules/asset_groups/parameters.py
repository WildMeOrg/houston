# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Asset_groups resources RESTful API
-----------------------------------------------------------
"""

from flask_restx_patched import Parameters, PatchJSONParameters
from flask_login import current_user  # NOQA

from . import schemas
from .models import AssetGroup
from app.modules.users.permissions import rules


class CreateAssetGroupParameters(Parameters, schemas.CreateAssetGroupSchema):
    class Meta(schemas.CreateAssetGroupSchema.Meta):
        pass


class PatchAssetGroupDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE, PatchJSONParameters.OP_ADD)

    PATH_CHOICES = tuple('/%s' % field for field in (AssetGroup.description.key, 'owner'))

    @classmethod
    def add(cls, obj, field, value, state):
        # Add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        from app.modules.users.models import User

        ret_val = False
        # Permissions for all fields are the same so have one check
        if rules.owner_or_privileged(current_user, obj) or current_user.is_admin:
            if field == AssetGroup.description.key:
                obj.description = value
                ret_val = True
            elif field == 'owner':
                user = User.query.get(value)
                if user:
                    obj.owner = user
                    ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        raise NotImplementedError()


class PatchAssetGroupSightingDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE, PatchJSONParameters.OP_ADD)
    VALID_FIELDS = ['config']
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def add(cls, obj, field, value, state):
        # Add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False
        # Permissions for all fields are the same so have one check
        if (
            current_user.is_privileged
            or current_user.is_admin
            or current_user.is_researcher
        ):
            if field == 'config':
                # The permissions check of what is allowed to be updated is done in the
                # PatchAssetGroupSightingMetadata, this assumes that the data is valid
                obj.meta = value
                ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        raise NotImplementedError()
