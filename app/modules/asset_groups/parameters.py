# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Asset_groups resources RESTful API
-----------------------------------------------------------
"""
import logging
import uuid

from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog
from app.modules.encounters.parameters import PatchEncounterDetailsParameters
from app.modules.sightings.parameters import PatchSightingDetailsParameters
from app.modules.users.permissions import rules
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .metadata import AssetGroupMetadata, AssetGroupMetadataError
from .models import AssetGroup

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


class PatchAssetGroupSightingDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )
    # These don't exist as entities in the AssetGroupSighting, they're just config blobs
    # but we allow patching faking them to be real
    # This uses the fact that anything that is an EDM sighting path is in the
    # AssetGroupSighting in the same format
    PATH_CHOICES = PatchSightingDetailsParameters.PATH_CHOICES_EDM + (
        '/idConfigs',
        '/assetReferences',
        '/name',
        '/time',
        '/timeSpecificity',
    )

    @classmethod
    def add(cls, obj, field, value, state):
        # Encounter is special in that it can only be added to an AssetGroupSightingDetails.
        if field == 'encounters':
            AssetGroupMetadata.validate_encounters(
                [
                    value,
                ],
                f'Sighting {obj.guid}',
            )
            # can assign annotations (in patch only) but they must be valid
            if 'annotations' in value:
                AssetGroupMetadata.validate_annotations(
                    obj, value['annotations'], f'Sighting {obj.guid}'
                )
            if 'encounters' not in obj.sighting_config.keys():
                obj.sighting_config['encounters'] = []

            # allocate pseudo ID for encounter
            value['guid'] = str(uuid.uuid4())
            obj.sighting_config['encounters'].append(value)

            # force write
            obj.config = obj.config
            return True
        elif field == 'assetReferences':
            # Raises AssetGroupMetadataError on error which is intentionally unnhandled
            cls.validate_asset_references(obj, [value])
            if value in obj.sighting_config.get('assetReferences', []):
                raise AssetGroupMetadataError(
                    log, f'{value} already in Group for assetGroupSighting {obj.guid}'
                )
            if 'assetReferences' in obj.sighting_config.keys():
                obj.sighting_config[field].append(value)
            else:
                obj.sighting_config[field] = [value]

            # force write
            obj.config = obj.config
            return True
        else:
            # Add and replace are the same operation for all other fields so reuse the one method
            return cls.replace(obj, field, value, state)

    # Asset ref patching is different enough from asset ref creation to not to be able to reuse the
    # metadata functionality
    @classmethod
    def validate_asset_references(cls, obj, asset_refs):
        for filename in asset_refs:

            # asset must exist and must be part of the group
            asset = obj.asset_group.get_asset_for_file(filename)
            if not asset:
                raise AssetGroupMetadataError(
                    log, f'{filename} not in Group for assetGroupSighting {obj.guid}'
                )
            # and must not be associated with another sighting
            ags_s = obj.asset_group.get_asset_group_sightings_for_asset(asset)
            if ags_s:
                if len(ags_s) != 1:
                    message = f'Asset {asset.guid} already in multiple AGS'
                    AuditLog.audit_log_object_fault(log, asset, message)
                    log.warning(message)
                if obj not in ags_s:
                    raise AssetGroupMetadataError(
                        log,
                        f'{filename} already in assetGroupSighting {ags_s[0].guid}, remove from this first.',
                    )

    @classmethod
    def replace(cls, obj, field, value, state):
        ret_val = False

        if field == 'config':
            # The permissions check of what is allowed to be updated is done in the
            # PatchAssetGroupSightingMetadata, this assumes that the data is valid
            obj.sighting_config = value
            ret_val = True
        elif field == 'idConfigs':
            # Raises AssetGroupMetadataError on error which is intentionally unnhandled
            AssetGroupMetadata.validate_id_configs(value, f'Sighting {obj.guid}')
            obj.sighting_config[field] = value
            ret_val = True
        elif field == 'encounters':
            # Does not make sense to replace an encounter
            ret_val = False
        elif field == 'assetReferences':
            # Only supports patch of all refs as one operation
            # Raises AssetGroupMetadataError on error which is intentionally unnhandled
            cls.validate_asset_references(obj, value)
            obj.sighting_config[field] = value
            ret_val = True
        else:
            obj.sighting_config[field] = value
            ret_val = True

        # Force the DB write
        if ret_val:
            obj.config = obj.config

        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        ret_val = False
        changed = False

        if field == 'encounters':
            # 'remove' passed for the encounter even if it wasn't there to start with
            ret_val = True
            if 'encounters' in obj.sighting_config.keys():
                if not isinstance(value, str):
                    # but fails for invalid value type
                    ret_val = False
                else:
                    for config_encounter in obj.sighting_config['encounters']:
                        if config_encounter['guid'] == value:
                            obj.sighting_config['encounters'].remove(config_encounter)
                            changed = True
        elif field == 'assetReferences':
            # always succeed. reference is remove or wasn't there. Either way it's not there anymore
            ret_val = True
            if value in obj.sighting_config.get('assetReferences', []):
                obj.sighting_config['assetReferences'].remove(value)
                changed = True
        if changed:
            # Force the DB write
            obj.config = obj.config

        return ret_val


# PATH_CHOICES and a couple of other methods are identical to the DetailsParameters class, only the replace
# is special
class PatchAssetGroupSightingAsSightingParameters(
    PatchAssetGroupSightingDetailsParameters
):
    # These don't exist as entities in the AssetGroupSighting, they're just config blobs
    # but we allow patching faking them to be real
    # This uses the fact that anything that is an EDM sighting path is in the
    # AssetGroupSighting in the same format
    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False

        # this is the only part with differing logic vs. PatchAssetGroupSightingDetailsParameters.
        # We will not get the 'config' field here bc it is not on Sightings. Any fields
        # in app.modules.asset_groups.schemas.SIGHTING_FIELDS_IN_AGS_CONFIG will be handled
        # by the final else case
        if field == 'idConfigs':
            # Raises AssetGroupMetadataError on error which is intentionally unnhandled
            AssetGroupMetadata.validate_id_configs(value, f'Sighting {obj.guid}')
            obj.sighting_config[field] = value
            ret_val = True
        elif field == 'encounters':
            # Does not make sense to replace an encounter
            ret_val = False
        elif field == 'assetReferences':
            # Only supports patch of all refs as one operation
            # Raises AssetGroupMetadataError on error which is intentionally unnhandled
            cls.validate_asset_references(obj, value)
            obj.sighting_config[field] = value
            ret_val = True
        else:
            obj.sighting_config[field] = value
            ret_val = True

        # Force the DB write
        obj.config = obj.config

        return ret_val


class PatchAssetGroupSightingEncounterDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )
    # These don't exist as entities in the AssetGroupSighting, they're just config blobs
    # but we allow patching faking them to be real

    PATH_CHOICES = PatchEncounterDetailsParameters.PATH_CHOICES_EDM + (
        '/ownerEmail',
        '/owner',  # Needed as that is the field name in the encounter that we're pretending to be
        '/time',
        '/timeSpecificity',
        '/annotations',
        '/individualUuid',
    )

    @classmethod
    def _get_encounter_data(cls, obj, encounter_uuid):
        encounter_metadata = obj.get_encounter_metadata(encounter_uuid)

        if not encounter_metadata:
            raise AssetGroupMetadataError(
                log,
                f'Encounter {encounter_uuid} not found in AssetGroupSighting {obj.guid}',
            )
        return encounter_metadata

    @classmethod
    def add(cls, obj, field, value, state):

        # For everything, Add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = True
        assert 'encounter_uuid' in state
        encounter_uuid = state['encounter_uuid']
        encounter_metadata = cls._get_encounter_data(obj, encounter_uuid)

        if field == 'ownerEmail':
            AssetGroupMetadata.validate_owner_email(value, f'Encounter {encounter_uuid}')
            encounter_metadata[field] = value
        elif field == 'owner':
            from app.modules.users.models import User

            user = User.query.get(value)
            if user and user.is_researcher:
                encounter_metadata['ownerEmail'] = user.email

        elif field == 'annotations':
            from app.modules.annotations.models import Annotation

            # Need to make it a list unless it's already one
            annot_guids = value if isinstance(value, list) else [value]

            AssetGroupMetadata.validate_annotations(
                obj,
                annot_guids,
                f'Encounter {encounter_uuid}',
            )
            for annot_guid in annot_guids:
                annot = Annotation.query.get(annot_guid)
                assert annot
                if (
                    annot.encounter
                    and not annot.encounter.current_user_has_write_access()
                ):
                    # No stealing annotations
                    raise AssetGroupMetadataError(
                        log,
                        f'You are not permitted to reassign {value} Annotation',
                    )
                # Probably a move from another encounter in the group. Remove it from all others first
                obj.asset_group.remove_annotation_from_any_sighting(annot_guid)

                obj.add_annotation_to_encounter(encounter_uuid, annot_guid)

        elif field == 'individualUuid':
            AssetGroupMetadata.validate_individual(value, f'Encounter {encounter_uuid}')
            encounter_metadata[field] = value
        else:
            encounter_metadata[field] = value
        # force the write to the database
        obj.config = obj.config
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        ret_val = False
        changed = False
        assert 'encounter_uuid' in state
        encounter_uuid = state['encounter_uuid']

        if field == 'annotations':
            if not isinstance(value, str):
                # but fails for invalid value type
                ret_val = False
            else:
                # 'remove' passed for the annotation even if it wasn't there to start with
                ret_val = True
                obj.remove_annotation_from_encounter(encounter_uuid, value)
                changed = True

        if changed:
            # Force the DB write
            obj.config = obj.config

        return ret_val
