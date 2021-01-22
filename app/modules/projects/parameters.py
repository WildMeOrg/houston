# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Projects resources RESTful API
-----------------------------------------------------------
"""

from flask_restplus_patched import Parameters
from app.houston import PatchJSONParametersWithPassword
from . import schemas
from .models import Project


class CreateProjectParameters(Parameters, schemas.DetailedProjectSchema):
    class Meta(schemas.DetailedProjectSchema.Meta):
        pass


class PatchProjectDetailsParameters(PatchJSONParametersWithPassword):
    # pylint: disable=abstract-method,missing-docstring

    # Valid options for patching are '/title', '/user' and '/encounter'.
    # The '/current_password' is not patchable but must be a valid field in the patch so that it can be
    # present for validation
    VALID_FIELDS = [
        Project.title.key,
        'current_password',
        'user',
        'encounter',
    ]
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def set_field(cls, obj, field, value, state):
        ret_val = True
        from app.modules.users.models import User
        from app.modules.encounters.models import Encounter

        if field == 'user':
            user = User.query.get(value)
            if user:
                obj.add_user(user)
            else:
                ret_val = False
        elif field == 'encounter':
            encounter = Encounter.query.get(value)
            if encounter:
                obj.add_encounter(encounter)
            else:
                ret_val = False
        return ret_val

    @classmethod
    def forget_field(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.encounters.models import Encounter

        # If the field wasn't present anyway, report that as a success
        if field == 'user':
            user = User.query.get(value)
            if user:
                obj.remove_user(user)
        elif field == 'encounter':
            encounter = Encounter.query.get(value)
            if encounter:
                obj.remove_encounter(encounter)
        return True

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
