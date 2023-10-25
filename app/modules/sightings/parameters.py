# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Sightings resources RESTful API
-----------------------------------------------------------
"""

import logging
from uuid import UUID

from flask_login import current_user

import app.modules.utils as util
from app.modules.users.permissions import rules
from app.modules.users.permissions.types import AccessOperation
from app.utils import CascadeDeleteException, HoustonException
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas

log = logging.getLogger(__name__)


class CreateSightingParameters(Parameters, schemas.CreateSightingSchema):
    class Meta(schemas.CreateSightingSchema.Meta):
        pass


class PatchSightingDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring

    OPERATION_CHOICES = (
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES = (
        '/idConfigs',
        '/assetId',
        '/featuredAssetGuid',
        '/name',
        '/time',
        '/timeSpecificity',
        '/comments',
        '/customFields',
        '/decimalLatitude',
        '/decimalLongitude',
        '/encounters',
        '/locationId',
        '/taxonomies',
        '/verbatimLocality',
        '/match_state',
    )

    @classmethod
    def add(cls, obj, field, value, state):
        if field == 'encounters':
            from app.modules.encounters.models import Encounter
            from app.modules.site_settings.models import Regions

            if not isinstance(value, dict):
                raise HoustonException(
                    log, 'can only add new Encounter using json object'
                )
            loc = value.get('locationId')

            if loc and not Regions.is_region_guid_valid(loc):
                raise HoustonException(log, f'Encounter add, locationId {loc} not found')

            new_encounter = Encounter(
                location_guid=loc,
                owner_guid=current_user.guid,
                decimal_latitude=value.get('decimalLatitude'),
                decimal_longitude=value.get('decimalLongitude'),
                taxonomy_guid=value.get('taxonomy'),
                verbatim_locality=value.get('verbatimLocality'),
                sex=value.get('sex'),
                custom_fields=value.get('customFields', {}),
            )
            obj.add_encounter(new_encounter)
            ret_val = True
        else:
            ret_val = cls.replace(obj, field, value, state)
        return ret_val

    @classmethod
    def replace(cls, obj, field, value, state):

        from datetime import datetime

        from app.modules.assets.models import Asset
        from app.modules.complex_date_time.models import ComplexDateTime

        ret_val = False

        has_permission = rules.ObjectActionRule(obj, AccessOperation.WRITE).check()

        if has_permission:

            if field == 'assetId' and util.is_valid_uuid_string(value):
                asset = Asset.query.get(value)
                if asset and (
                    asset.git_store.owner == current_user or current_user.is_admin
                ):
                    obj.add_asset(asset)
                    ret_val = True

            elif field == 'featuredAssetGuid' and util.is_valid_uuid_string(value):
                obj.set_featured_asset_guid(UUID(value, version=4))
                ret_val = True

            elif field == 'name':
                obj.name = value
                ret_val = True

            elif field == 'time' or field == 'timeSpecificity':
                ret_val = ComplexDateTime.patch_replace_helper(obj, field, value)
            elif field == 'idConfigs':
                from app.modules.asset_groups.metadata import AssetGroupMetadata

                # Raises AssetGroupMetadataError on error which is intentionally unnhandled
                AssetGroupMetadata.validate_id_configs(value, f'Sighting {obj.guid}')
                obj.id_configs = value
                ret_val = True

            # Encounters and taxonomies patch explicitly not supported

            elif field == 'comments':
                obj.comments = value
                ret_val = True
            elif field == 'customFields':
                # see explanation on encounter patch
                assert isinstance(
                    value, dict
                ), 'customFields must be passed a json object'
                if value.get('id'):
                    assert 'value' in value, 'customFields id/value format needs both'
                    value = {value['id']: value['value']}
                obj.set_custom_field_values_json(value)  # does all the validation etc
                ret_val = True
            elif field == 'decimalLatitude':
                if value and not util.is_valid_latitude(value):
                    raise HoustonException(
                        log, f'decimalLatitude value passed ({value}) is invalid'
                    )
                obj.decimal_latitude = value
                ret_val = True
            elif field == 'decimalLongitude':
                if value and not util.is_valid_longitude(value):
                    raise HoustonException(
                        log, f'decimalLongitude value passed ({value}) is invalid'
                    )
                obj.decimal_longitude = value
                ret_val = True
            elif field == 'locationId':
                from app.modules.site_settings.models import Regions

                if value and not Regions.is_region_guid_valid(value):
                    raise HoustonException(
                        log,
                        f'locationId value passed ({value}) is not a valid guid for a Region',
                    )
                obj.location_guid = value
                ret_val = True
            elif field == 'verbatimLocality':
                obj.verbatim_locality = value
                ret_val = True
            elif field == 'match_state':
                from app.modules.sightings.models import SightingMatchState

                try:
                    SightingMatchState(value)
                except KeyError:
                    raise HoustonException(
                        log, f'match_state value passed ({value}) is invalid'
                    )
                obj.match_state = value
                if (
                    value == SightingMatchState.reviewed
                    or value == SightingMatchState.unidentifiable
                ):
                    obj.review_time = datetime.utcnow()
                ret_val = True

        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        ret_val = False
        if field == 'encounters':
            assert 'delete-individual' in state, 'delete-individual missing from state'
            assert 'delete-sighting' in state, 'delete-sighting missing from state'

            from app.modules.encounters.models import Encounter

            enc = Encounter.query.get(value)
            deleted_individual_guid = None
            vulnerable_individual_guid = None
            deleted_sighting_guid = None
            vulnerable_sighting_guid = None

            # No removing another sighting's encounter
            if enc and enc.sighting == obj:
                if enc.individual and len(enc.individual.encounters) == 1:
                    if state['delete-individual']:
                        deleted_individual_guid = enc.individual.guid
                        enc.individual.delete()
                    else:
                        vulnerable_individual_guid = enc.individual.guid
                if len(obj.encounters) == 1:
                    if state['delete-sighting']:
                        deleted_sighting_guid = obj.guid
                        obj.delete_cascade()
                    else:
                        vulnerable_sighting_guid = obj.guid
                vulnerable_sightings = (
                    [vulnerable_sighting_guid] if vulnerable_sighting_guid else []
                )
                vulnerable_individuals = (
                    [vulnerable_individual_guid] if vulnerable_individual_guid else []
                )
                deleted_sightings = (
                    [deleted_sighting_guid] if deleted_sighting_guid else []
                )
                deleted_individuals = (
                    [deleted_individual_guid] if deleted_individual_guid else []
                )
                # If any are vulnerable, the encounter is not deleted and we inform the calling code
                if vulnerable_individual_guid or vulnerable_sighting_guid:
                    raise CascadeDeleteException(
                        vulnerableSightingGuids=vulnerable_sightings,
                        vulnerableIndividualGuids=vulnerable_individuals,
                    )
                if deleted_sighting_guid:
                    # special case, the sighting has been deleted so in this instance we do not need to
                    # delete the encounter as it's already gone, we just need to inform the caller
                    raise CascadeDeleteException(
                        deletedSightingGuids=deleted_sightings,
                        deletedIndividualGuids=deleted_individuals,
                    )
                obj.remove_encounter(enc)
                enc.delete()

                if deleted_individual_guid:
                    # still need to inform caller that individual was removed
                    raise CascadeDeleteException(
                        deletedIndividualGuids=deleted_individuals
                    )

            ret_val = True
        return ret_val
