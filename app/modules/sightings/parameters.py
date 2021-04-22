# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Sightings resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields

from flask_restx_patched.parameters import PatchJSONParametersWithPassword
from flask_login import current_user
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas

from app.modules.users.permissions import rules


class CreateSightingParameters(Parameters, schemas.DetailedSightingSchema):
    class Meta(schemas.DetailedSightingSchema.Meta):
        pass


class PatchSightingDetailsParameters(PatchJSONParametersWithPassword):
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
        '/assetId',
        '/newSubmission',
    )

    PATH_CHOICES_HOUSTON = ('assetId', 'newAssetGroup')

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

    @classmethod
    def add(cls, obj, field, value, state):
        from app.modules.assets.models import Asset
        from app.modules.submissions.models import Submission

        super(PatchSightingDetailsParameters, cls).add(obj, field, value, state)
        ret_val = False

        if rules.owner_or_privileged(current_user, obj):

            if field == 'assetId':
                asset = Asset.query.get(value)
                if asset and asset.submission.owner == current_user:
                    obj.add_asset(asset)
                    ret_val = True

            elif field == 'newSubmission':
                new_submission = Submission.create_submission_from_tus(
                    'Encounter.patch' + value, current_user, value
                )

                for asset in new_submission.assets:
                    obj.add_asset(asset)
                ret_val = True

        return ret_val
