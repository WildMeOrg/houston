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

    # Valid options for patching are '/title', '/User', and '/Encounter'.
    # The '/current_password' is not patchable but must be a valid field in the patch so that it can be
    # present for validation

    VALID_FIELDS = [Project.title.key, 'current_password', 'User', 'Encounter']
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def set_field(cls, obj, field, value, state):
        return obj.set_field(field, value)

    @classmethod
    def forget_field(cls, obj, field, state):
        return obj.forget_field(field)

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
