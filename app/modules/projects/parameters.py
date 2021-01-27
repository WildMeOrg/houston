# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Projects resources RESTful API
-----------------------------------------------------------
"""

from flask_login import current_user  # NOQA
from flask_restplus_patched import Parameters, PatchJSONParametersWithPassword
from . import schemas
from .models import Project
from app.modules.users.permissions.rules import user_is_privileged


class CreateProjectParameters(Parameters, schemas.DetailedProjectSchema):
    class Meta(schemas.DetailedProjectSchema.Meta):
        pass


class PatchProjectDetailsParameters(PatchJSONParametersWithPassword):
    # pylint: disable=abstract-method,missing-docstring

    # Valid options for patching are '/title', '/user' and '/encounter'.
    # The '/current_password' is not patchable but must be a valid field in the patch so that it can be
    # present for validation
    VALID_FIELDS = [Project.title.key, 'current_password', 'user', 'encounter', 'owner']
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def owner_or_privileged(cls, user, obj):
        return user == obj.owner or user_is_privileged(user, obj)

    @classmethod
    def add(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.encounters.models import Encounter

        super(PatchProjectDetailsParameters, cls).add(obj, field, value, state)
        ret_val = False

        if field == Project.title.key:
            if cls.owner_or_privileged(current_user, obj):
                obj.title = value
                ret_val = True
        elif field == 'owner':
            # owner is permitted to assign project ownership to another member
            user = User.query.get(value)
            if (
                cls.owner_or_privileged(current_user, obj)
                and user
                and user in obj.members
            ):
                obj.owner = user
                ret_val = True
        elif field == 'user':
            # Only project owners or privileged users can add and delete users
            user = User.query.get(value)
            if cls.owner_or_privileged(current_user, obj) and user:
                obj.add_user_in_context(user)
                ret_val = True
        elif field == 'encounter':
            encounter = Encounter.query.get(value)
            if encounter and (
                current_user in obj.members or user_is_privileged(current_user, obj)
            ):
                obj.add_encounter_in_context(encounter)
                ret_val = True

        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.encounters.models import Encounter

        super(PatchProjectDetailsParameters, cls).remove(obj, field, value, state)

        ret_val = True

        # If the field wasn't present anyway, report that as a success
        # A failure is if the user did not have permission to perform the action
        if field == Project.title.key or field == 'owner':
            # no one deletes the owner or title
            ret_val = False
        elif field == 'user':
            user = User.query.get(value)

            if not cls.owner_or_privileged(current_user, obj):
                ret_val = False
            elif user:
                # Don't allow owner to accidentally remove themselves, would only cause a maintenance nightmare
                if user == current_user:
                    ret_val = False
                else:
                    obj.remove_user_in_context(user)
        elif field == 'encounter':
            encounter = Encounter.query.get(value)
            if current_user not in obj.members and not user_is_privileged(current_user):
                ret_val = False
            elif encounter:
                obj.remove_encounter_assume_context(encounter)
        return ret_val

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
