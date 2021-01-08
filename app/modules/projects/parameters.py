# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Projects resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restplus_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import Project


class CreateProjectParameters(Parameters, schemas.DetailedProjectSchema):
    class Meta(schemas.DetailedProjectSchema.Meta):
        pass


class PatchProjectDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    PATH_CHOICES = tuple('/%s' % field for field in (Project.title.key,))
