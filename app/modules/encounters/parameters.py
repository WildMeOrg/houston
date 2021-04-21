# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Encounters resources RESTful API
-----------------------------------------------------------
"""

from flask_login import current_user
from flask_restx_patched import Parameters, PatchJSONParametersWithPassword

from . import schemas

from app.modules.users.permissions import rules


class CreateEncounterParameters(Parameters, schemas.DetailedEncounterSchema):
    class Meta(schemas.DetailedEncounterSchema.Meta):
        pass


class PatchEncounterDetailsParameters(PatchJSONParametersWithPassword):
    # pylint: disable=abstract-method,missing-docstring

    # Valid options for patching are replace '/owner', and add '/assetId' and '/newAssetGroup'
    # The '/current_password' and '/user' are not patchable but must be valid fields in the patch so that
    #  they can be present for validation
    VALID_FIELDS = ['current_password', 'user', 'owner']
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def replace(cls, obj, field, value, state):
        from app.modules.users.models import User

        super(PatchEncounterDetailsParameters, cls).replace(obj, field, value, state)
        ret_val = False
        if field == 'owner':
            # owner is permitted to assign ownership to another researcher
            user = User.query.get(value)
            if (
                rules.owner_or_privileged(current_user, obj)
                and user
                and user.is_researcher
            ):
                obj.owner = user
                ret_val = True

        return ret_val

        # @classmethod
        # def add(cls, obj, field, value, state):
        #     from app.modules.assets.models import Asset
        #     from app.modules.submissions.models import Submission

        #     super(PatchEncounterDetailsParameters, cls).add(obj, field, value, state)
        #     ret_val = False

        #     if rules.owner_or_privileged(current_user, obj):
        #         if field == 'assetId':
        #             asset = Asset.query.get(value)
        #             if asset and asset.submission.owner == current_user:
        #                 obj.add_asset(asset)
        #                 ret_val = True

        #         elif field == 'newSubmission':
        #             new_submission = Submission.create_submission_from_tus(
        #                 'Encounter.patch' + value, current_user, value
        #             )

        #             #need to move work to sighting

        #             for asset in new_submission.assets:
        #                 obj.add_asset(asset)
        #             ret_val = True

        return ret_val
