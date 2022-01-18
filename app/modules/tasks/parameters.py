# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Tasks resources RESTful API
-----------------------------------------------------------
"""

from flask_login import current_user  # NOQA
from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas
from .models import Task
from app.modules.users.permissions import rules


class CreateTaskParameters(Parameters, schemas.DetailedTaskSchema):
    class Meta(schemas.DetailedTaskSchema.Meta):
        pass


class PatchTaskDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring

    # Valid options for patching are '/title' and '/user'
    # The '/current_password' is not patchable but must be a valid field in the patch so that it can be
    # present for validation
    VALID_FIELDS = [Task.title.key, 'current_password', 'user', 'owner']
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def add(cls, obj, field, value, state):
        from app.modules.users.models import User

        super(PatchTaskDetailsParameters, cls).add(obj, field, value, state)
        ret_val = False

        if field == Task.title.key:
            if rules.owner_or_privileged(current_user, obj):
                obj.title = value
                ret_val = True
        elif field == 'owner':
            # owner is permitted to assign task ownership to another member
            user = User.query.get(value)
            if (
                rules.owner_or_privileged(current_user, obj)
                and user
                and user in obj.get_members()
            ):
                obj.owner = user
                ret_val = True
        elif field == 'user':
            # Only task owners or privileged users can add users
            user = User.query.get(value)
            if rules.owner_or_privileged(current_user, obj) and user:
                obj.add_user_in_context(user)
                ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        from app.modules.users.models import User

        super(PatchTaskDetailsParameters, cls).remove(obj, field, value, state)

        ret_val = True
        # If the field wasn't present anyway, report that as a success
        # A failure is if the user did not have permission to perform the action
        if field == Task.title.key or field == 'owner':
            # no one deletes the owner or title
            ret_val = False
        elif field == 'user':
            user = User.query.get(value)

            # make sure it's a valid request
            if not user or user not in obj.get_members():
                ret_val = False
            elif user == obj.owner:
                # Deleting the Task owner would cause a maintenance nightmare so disallow it
                ret_val = False
            elif rules.owner_or_privileged(current_user, obj):
                # removal of other users requires privileges
                obj.remove_user_in_context(user)
            elif user == current_user:
                # any user can delete themselves
                obj.remove_user_in_context(user)
            else:
                # but not other members
                ret_val = False

        return ret_val

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
