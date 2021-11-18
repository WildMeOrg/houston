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

    PATH_CHOICES_EDM = (
        '/comments',
        '/customFields',
        '/decimalLatitude',
        '/decimalLongitude',
        '/locationId',
        '/sex',
        '/taxonomy',
        '/time',
        '/verbatimLocality',
    )

    # Valid options for patching are replace '/owner'
    # The '/current_password' and '/user' are not patchable but must be valid fields in the patch so that
    #  they can be present for validation
    PATH_CHOICES_HOUSTON = ('/current_password', '/user', '/owner')

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

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
