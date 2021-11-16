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
    )

    PATH_CHOICES_HOUSTON = (
        '/assetId',
        '/newAssetGroup',
        '/featuredAssetGuid',
        '/name',
        '/stage',
    )

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

    COMPLEX_PATH_CHOICES = PATH_CHOICES_HOUSTON

    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        from app.modules.assets.models import Asset
        from app.modules.asset_groups.models import AssetGroup

        if ('/' + field) not in PatchSightingDetailsParameters.COMPLEX_PATH_CHOICES:
            super(PatchSightingDetailsParameters, cls).add(obj, field, value, state)

        ret_val = False

        has_permission = rules.ObjectActionRule(obj, AccessOperation.WRITE).check()

        if has_permission:

            if field == 'assetId' and util.is_valid_guid(value):
                asset = Asset.query.get(value)
                if asset and (
                    asset.asset_group.owner == current_user or current_user.is_admin
                ):
                    obj.add_asset(asset)
                    ret_val = True

            elif field == 'newAssetGroup':

                new_asset_group = AssetGroup.create_from_tus(
                    'Sighting.patch' + value, current_user, value
                )

                for asset in new_asset_group.assets:
                    obj.add_asset(asset)
                ret_val = True

            elif field == 'featuredAssetGuid' and util.is_valid_guid(value):
                obj.set_featured_asset_guid(UUID(value, version=4))
                ret_val = True

            elif field == 'name':
                obj.name = value
                ret_val = True

            # TODO is this correct, do we know yet how a sighting should be marked as being done?
            elif field == 'stage':
                from app.modules.sightings.models import SightingStage

                # TODO this is definitely wrong as it should be one or the other
                if value == 'processed' and obj.stage in set(
                    {SightingStage.un_reviewed, SightingStage.identification}
                ):
                    obj.stage = SightingStage.processed
                    ret_val = True
        return ret_val
