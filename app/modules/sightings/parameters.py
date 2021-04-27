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


class CreateSightingParameters(Parameters, schemas.DetailedSightingSchema):
    class Meta(schemas.DetailedSightingSchema.Meta):
        pass


class PatchSightingDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring

    OPERATION_CHOICES = (
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES_EDM = (
        '/bearing',
        '/behavior',
        '/comments',
        '/context',
        '/decimalLatitude',
        '/decimalLongitude',
        '/distance',
        '/endTime',
        '/locationId',
        '/startTime',
        '/taxonomies',
        '/verbatimLocality',
    )

    PATH_CHOICES_HOUSTON = ('/assetId', '/newAssetGroup')

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

    COMPLEX_PATH_CHOICES = PATH_CHOICES_HOUSTON

    @classmethod
    def add(cls, obj, field, value, state):
        from app.modules.assets.models import Asset
        from app.modules.asset_groups.models import AssetGroup

        if ('/' + field) not in PatchSightingDetailsParameters.COMPLEX_PATH_CHOICES:
            super(PatchSightingDetailsParameters, cls).add(obj, field, value, state)

        ret_val = False

        has_permission = rules.ObjectActionRule(obj, AccessOperation.WRITE).check()
        if has_permission:

            if field == 'assetId':
                asset = Asset.query.get(value)
                if asset and asset.asset_group.owner == current_user:
                    obj.add_asset(asset)
                    ret_val = True

            elif field == 'newAssetGroup':

                new_asset_group = AssetGroup.create_from_tus(
                    'Sighting.patch' + value, current_user, value
                )

                for asset in new_asset_group.assets:
                    obj.add_asset(asset)
                ret_val = True

        return ret_val
