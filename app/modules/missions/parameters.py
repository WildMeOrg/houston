# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Missions resources RESTful API
-----------------------------------------------------------
"""

from flask_login import current_user  # NOQA
from flask_marshmallow import base_fields
from flask_restx_patched import (
    Parameters,
    PatchJSONParameters,
    PatchJSONParametersWithPassword,
)
from app.extensions.api.parameters import PaginationParameters

from . import schemas
from .models import Mission, MissionCollection, MissionTask
from app.modules.users.permissions import rules


class ListMissionParameters(PaginationParameters):
    """
    New user creation (sign up) parameters.
    """

    search = base_fields.String(description='Example: search@example.com', required=False)


class CreateMissionParameters(Parameters, schemas.CreationMissionSchema):
    class Meta(schemas.CreationMissionSchema.Meta):
        pass


class PatchMissionDetailsParameters(PatchJSONParametersWithPassword):
    # pylint: disable=abstract-method,missing-docstring

    VALID_FIELDS = [
        'current_password',
        'owner',
        'user',
        'asset',
        Mission.title.key,
        Mission.options.key,
        Mission.classifications.key,
        Mission.notes.key,
    ]

    SENSITIVE_FIELDS = (
        'owner',
        'user',
    )

    PRIVILEGED_FIELDS = ()

    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def replace(cls, obj, field, value, state):
        from app.modules.users.models import User

        ret_val = False

        # Permissions for all fields are the same so have one check
        if field == 'owner' and (
            rules.owner_or_privileged(current_user, obj) or current_user.is_admin
        ):
            user = User.query.get(value)
            if user:
                obj.owner = user
                ret_val = True
        else:
            ret_val = super(PatchMissionDetailsParameters, cls).replace(
                obj, field, value, state
            )

        return ret_val

    @classmethod
    def add(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.assets.models import Asset

        # Check permissions
        super(PatchMissionDetailsParameters, cls).add(obj, field, value, state)

        ret_val = False

        if field == 'user':
            # Only mission owners or privileged users can add users
            user = User.query.get(value)
            if rules.owner_or_privileged(current_user, obj) and user:
                obj.add_user_in_context(user)
                ret_val = True
        elif field == 'asset':
            asset = Asset.query.get(value)
            if rules.owner_or_privileged(current_user, obj) and user:
                obj.add_asset_in_context(asset)
                ret_val = True

        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.assets.models import Asset

        # Check permissions
        super(PatchMissionDetailsParameters, cls).remove(obj, field, value, state)

        ret_val = False

        if field == 'user':
            user = User.query.get(value)

            # make sure it's a valid request
            if not user or user not in obj.get_members():
                pass
            elif user == obj.owner:
                # Deleting the Mission owner would cause a maintenance nightmare so disallow it
                pass
            elif rules.owner_or_privileged(current_user, obj):
                # removal of other users requires privileges
                obj.remove_user_in_context(user)
                ret_val = True
            elif user == current_user:
                # any user can delete themselves
                obj.remove_user_in_context(user)
                ret_val = True
        elif field == 'asset':
            asset = Asset.query.get(value)

            # make sure it's a valid request
            if not asset or asset not in obj.get_assets():
                pass
            elif rules.owner_or_privileged(current_user, obj):
                # removal of other users requires privileges
                obj.remove_asset_in_context(asset)
                ret_val = True

        return ret_val


class ListMissionCollectionParameters(PaginationParameters):
    search = base_fields.String(description='Example: search@example.com', required=False)


class CreateMissionCollectionParameters(Parameters):
    description = base_fields.String(
        description='The description for the Mission Collection', required=True
    )
    transaction_id = base_fields.String(
        description='The TUS transaction ID to import images from', required=True
    )


class PatchMissionCollectionDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE, PatchJSONParameters.OP_ADD)

    SENSITIVE_FIELDS = []

    PRIVILEGED_FIELDS = []

    VALID_FIELDS = [
        MissionCollection.description.key,
        'owner',
    ]

    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

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
            if field == MissionCollection.description.key:
                obj.description = value
                ret_val = True
            elif field == 'owner':
                user = User.query.get(value)
                if user:
                    obj.owner = user
                    ret_val = True
        return ret_val


class ListMissionTaskParameters(PaginationParameters):
    search = base_fields.String(description='Example: search@example.com', required=False)


class CreateMissionTaskParameters(Parameters):
    title = base_fields.String(description='The title of the Mission Task', required=True)


class PatchMissionTaskDetailsParameters(PatchJSONParametersWithPassword):
    # pylint: disable=abstract-method,missing-docstring

    # Valid options for patching are '/title' and '/user'
    # The '/current_password' is not patchable but must be a valid field in the patch so that it can be
    # present for validation
    VALID_FIELDS = [
        'current_password',
        'owner',
        'user',
        'asset',
        MissionTask.title.key,
    ]

    SENSITIVE_FIELDS = (
        'owner',
        'user',
    )

    PRIVILEGED_FIELDS = ()

    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def add(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.assets.models import Asset

        super(PatchMissionTaskDetailsParameters, cls).add(obj, field, value, state)
        ret_val = False

        if field == MissionTask.title.key:
            if rules.owner_or_privileged(current_user, obj):
                obj.title = value
                ret_val = True
        elif field == 'owner':
            # owner is permitted to assign task ownership to another member
            user = User.query.get(value)
            if (
                rules.owner_or_privileged(current_user, obj)
                and user
                and user in obj.get_members()
            ):
                obj.owner = user
                ret_val = True
        elif field == 'user':
            # Only task owners or privileged users can add users
            user = User.query.get(value)
            if rules.owner_or_privileged(current_user, obj) and user:
                obj.add_user_in_context(user)
                ret_val = True
        elif field == 'asset':
            asset = Asset.query.get(value)
            if rules.owner_or_privileged(current_user, obj) and user:
                obj.add_asset_in_context(asset)
                ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.assets.models import Asset

        super(PatchMissionTaskDetailsParameters, cls).remove(obj, field, value, state)

        ret_val = True
        # If the field wasn't present anyway, report that as a success
        # A failure is if the user did not have permissions to perform the action
        if field == MissionTask.title.key or field == 'owner':
            # no one deletes the owner or title
            ret_val = False
        elif field == 'user':
            user = User.query.get(value)

            # make sure it's a valid request
            if not user or user not in obj.get_members():
                ret_val = False
            elif user == obj.owner:
                # Deleting the MissionTask owner would cause a maintenance nightmare so disallow it
                ret_val = False
            elif rules.owner_or_privileged(current_user, obj):
                # removal of other users requires privileges
                obj.remove_user_in_context(user)
            elif user == current_user:
                # any user can delete themselves
                obj.remove_user_in_context(user)
            else:
                # but not other members
                ret_val = False
        elif field == 'asset':
            asset = Asset.query.get(value)

            # make sure it's a valid request
            if not asset or asset not in obj.get_assets():
                ret_val = False
            elif rules.owner_or_privileged(current_user, obj):
                # removal of other users requires privileges
                obj.remove_asset_in_context(asset)
            else:
                # but not other members
                ret_val = False

        return ret_val

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
