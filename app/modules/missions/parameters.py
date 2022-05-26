# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Missions resources RESTful API
-----------------------------------------------------------
"""

import logging

from flask_login import current_user  # NOQA
from flask_marshmallow import base_fields
from marshmallow import ValidationError

from app.modules.users.permissions import rules
from flask_restx_patched import (
    Parameters,
    PatchJSONParameters,
    PatchJSONParametersWithPassword,
    SetOperationsJSONParameters,
)

from . import schemas
from .models import Mission, MissionCollection, MissionTask

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class CreateMissionParameters(Parameters, schemas.CreationMissionSchema):
    class Meta(schemas.CreationMissionSchema.Meta):
        pass


class PatchMissionDetailsParameters(PatchJSONParametersWithPassword):
    # pylint: disable=abstract-method,missing-docstring

    VALID_FIELDS = [
        'current_password',
        'owner',
        'user',
        Mission.title.key,
        Mission.options.key,
        Mission.notes.key,
    ]

    SENSITIVE_FIELDS = ('owner',)

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
        from app.modules.assets.models import Asset
        from app.modules.users.models import User

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
        from app.modules.assets.models import Asset
        from app.modules.users.models import User

        # Check permissions
        super(PatchMissionDetailsParameters, cls).remove(obj, field, value, state)

        ret_val = False

        if field == 'user':
            user = User.query.get(value)

            # make sure it's a valid request
            if not user:
                pass
            elif user not in obj.get_members():
                ret_val = True
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
            if not asset:
                pass
            elif asset not in obj.get_assets():
                ret_val = True
            elif rules.owner_or_privileged(current_user, obj):
                # removal of other users requires privileges
                obj.remove_asset_in_context(asset)
                ret_val = True

        return ret_val


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


class CreateMissionTaskParameters(SetOperationsJSONParameters):
    # pylint: disable=abstract-method,missing-docstring

    VALID_FIELDS = [
        'search',
        'collections',
        'tasks',
        'assets',
    ]

    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def resolve(cls, field, value, obj):
        from app.modules.assets.models import Asset
        from app.modules.missions.models import MissionCollection, MissionTask

        def _check(condition):
            if not condition:
                raise ValidationError(
                    'Failed to update set. Operation (field=%r, value=%r) could not succeed because the value must be a list of string GUIDs.'
                    % (field, value)
                )

        if field == 'search':
            return obj.asset_search(value, total=False, limit=None)
        elif field == 'collections':
            assets = []

            _check(isinstance(value, list))
            for guid in value:
                _check(isinstance(guid, str))
                mission_collection = MissionCollection.query.get(guid)
                if mission_collection is not None:
                    if mission_collection.mission == obj:
                        assets += mission_collection.assets
                    else:
                        raise ValidationError(
                            'Failed to update set. Mission Collection %r is not part of Mission %r'
                            % (mission_collection.guid, obj.guid)
                        )

            return assets
        elif field == 'tasks':
            assets = []

            _check(isinstance(value, list))
            for guid in value:
                _check(isinstance(guid, str))
                mission_task = MissionTask.query.get(guid)
                if mission_task is not None:
                    if mission_task.mission == obj:
                        assets += mission_task.assets
                    else:
                        raise ValidationError(
                            'Failed to update set. Mission Task %r is not part of Mission %r'
                            % (mission_task.guid, obj.guid)
                        )

            return assets
        elif field == 'assets':
            assets = []

            _check(isinstance(value, list))
            for guid in value:
                _check(isinstance(guid, str))
                asset = Asset.query.get(guid)
                if asset is not None:
                    if asset.git_store.mission == obj:
                        assets.append(asset)
                    else:
                        raise ValidationError(
                            'Failed to update set. Asset %r is not part of any Mission Collection for Mission %r'
                            % (asset.guid, obj.guid)
                        )

            return assets

        return None


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

    SENSITIVE_FIELDS = ('owner',)

    PRIVILEGED_FIELDS = ()

    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def add(cls, obj, field, value, state):
        from app.modules.assets.models import Asset
        from app.modules.users.models import User

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
        from app.modules.assets.models import Asset
        from app.modules.users.models import User

        # Check permissions
        super(PatchMissionTaskDetailsParameters, cls).remove(obj, field, value, state)

        ret_val = False

        if field == 'user':
            user = User.query.get(value)

            # make sure it's a valid request
            if not user:
                pass
            elif user not in obj.get_members():
                ret_val = True
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
            if not asset:
                pass
            elif asset not in obj.get_assets():
                ret_val = True
            elif rules.owner_or_privileged(current_user, obj):
                # removal of other users requires privileges
                obj.remove_asset_in_context(asset)
                ret_val = True

        return ret_val

    @classmethod
    def replace(cls, obj, field, value, state):
        from app.modules.users.models import User

        ret_val = False
        # Permissions for all fields are the same so have one check
        if rules.owner_or_privileged(current_user, obj) or current_user.is_admin:
            if field == MissionTask.title.key:
                obj.title = value
                ret_val = True
            elif field == 'owner':
                user = User.query.get(value)
                if user:
                    obj.owner = user
                    ret_val = True
        return ret_val
