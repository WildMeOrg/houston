# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Asset_groups resources RESTful API
-----------------------------------------------------------
"""
import logging
import uuid

from flask_restx_patched import Parameters, PatchJSONParameters
from flask_login import current_user  # NOQA

from . import schemas
from .models import AssetGroup
from app.modules.users.permissions import rules

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


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
    # These don't exist as entities in the AssetGroupSighting, they're just config blobs
    # but we allow patching faking them to be real
    PATH_CHOICES = (
        '/bearing',
        '/behavior',
        '/comments',
        '/context',
        '/customFields',
        '/decimalLatitude',
        '/decimalLongitude',
        '/distance',
        '/encounters',
        '/endTime',
        '/locationId',
        '/startTime',
        '/taxonomies',
        '/verbatimLocality',
        '/idConfigs',
        '/assetReferences',
        # TODO name not implemented, should it be?
    )

    @classmethod
    def add(cls, obj, field, value, state):
        # Add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    # Asset ref patching is different enough from asset ref creation to not to be able to reuse the
    # metadata functionality
    @classmethod
    def validate_asset_references(cls, obj, asset_refs):
        from .metadata import AssetGroupMetadataError

        for filename in asset_refs:
            # asset must exist and must be part of the group
            if not obj.asset_group.get_asset_for_file(filename):
                raise AssetGroupMetadataError(
                    f'{filename} not in Group for assetGroupSighting {obj.guid}'
                )

    @classmethod
    def replace(cls, obj, field, value, state):
        # Reuse metadata methods to validate ID Config
        from .metadata import AssetGroupMetadata

        ret_val = False

        if field == 'config':
            # The permissions check of what is allowed to be updated is done in the
            # PatchAssetGroupSightingMetadata, this assumes that the data is valid
            obj.config = value
            ret_val = True
        elif field == 'idConfigs':
            # Raises AssetGroupMetadataError on error which is intentionally unnhandled
            AssetGroupMetadata.validate_id_configs(value, f'Sighting {obj.guid}')
            obj.config[field] = value
            ret_val = True
        elif field == 'encounters':
            AssetGroupMetadata.validate_encounters(value, f'Sighting {obj.guid}')
            obj.config[field] = value
            # All encounters in the metadata need to be allocated a pseudo ID for later patching
            for encounter_num in range(len(obj.config['encounters'])):
                if 'guid' not in obj.config['encounters'][encounter_num]:
                    obj.config['encounters'][encounter_num]['guid'] = str(uuid.uuid4())
            ret_val = True
        elif field == 'assetReferences':
            # Only supports patch of all refs as one operation
            # Raises AssetGroupMetadataError on error which is intentionally unnhandled
            cls.validate_asset_references(obj, value)
            obj.config[field] = value
            ret_val = True
        else:
            obj.config[field] = value
            ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        raise NotImplementedError()


class PatchAssetGroupSightingEncounterDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE, PatchJSONParameters.OP_ADD)
    # These don't exist as entities in the AssetGroupSighting, they're just config blobs
    # but we allow patching faking them to be real
    PATH_CHOICES = (
        '/behavior',
        '/comments',
        '/customFields',
        '/decimalLatitude',
        '/decimalLongitude',
        '/lifeStage',
        '/locationId',
        '/sex',
        '/taxonomy',
        '/time',
        '/timeValues',
        '/verbatimLocality',
        '/ownerEmail',
        '/annotations',
        # TODO name and individualUuid are not here, should they be?
    )

    @classmethod
    def add(cls, obj, field, value, state):
        # Add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        # Reuse metadata methods to validate fields
        from .metadata import AssetGroupMetadata, AssetGroupMetadataError

        ret_val = False

        assert 'encounter_uuid' in state
        encounter_uuid = state['encounter_uuid']
        encounter_metadata = {}
        for encounter_num in range(len(obj.config['encounters'])):
            if obj.config['encounters'][encounter_num]['guid'] == str(encounter_uuid):
                encounter_metadata = obj.config['encounters'][encounter_num]
                break
        if not encounter_metadata:
            raise AssetGroupMetadataError(
                f'Encounter {encounter_uuid} not found in AssetGroupSighting {obj.guid}'
            )

        if field == 'ownerEmail':
            AssetGroupMetadata.validate_owner_email(value, f'Encounter {encounter_uuid}')
            encounter_metadata[field] = value
            ret_val = True
        elif field == 'annotations':
            AssetGroupMetadata.validate_annotations(value, f'Encounter {encounter_uuid}')
            encounter_metadata[field] = value
            ret_val = True
        else:
            encounter_metadata[field] = value
            ret_val = True
        # force the write to the database
        obj.config = obj.config
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        raise NotImplementedError()
