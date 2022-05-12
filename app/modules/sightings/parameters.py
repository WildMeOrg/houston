# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Sightings resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields

from flask_login import current_user
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas

from app.modules.users.permissions.types import AccessOperation
from app.modules.users.permissions import rules

import app.modules.utils as util
from uuid import UUID


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

    PATH_CHOICES_EDM = (
        '/comments',
        '/customFields',
        '/decimalLatitude',
        '/decimalLongitude',
        '/encounters',
        '/locationId',
        '/taxonomies',
        '/verbatimLocality',
        '/verbatimEventDate',
    )

    PATH_CHOICES_HOUSTON = (
        '/idConfigs',
        '/assetId',
        '/featuredAssetGuid',
        '/name',
        '/time',
        '/timeSpecificity',
    )

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

    COMPLEX_PATH_CHOICES = PATH_CHOICES_HOUSTON

    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        from app.modules.assets.models import Asset
        from app.modules.complex_date_time.models import ComplexDateTime

        if ('/' + field) not in PatchSightingDetailsParameters.COMPLEX_PATH_CHOICES:
            super(PatchSightingDetailsParameters, cls).add(obj, field, value, state)

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
        return ret_val
