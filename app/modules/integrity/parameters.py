# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Integrity resources RESTful API
-----------------------------------------------------------
"""

from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import Integrity


class CreateIntegrityParameters(Parameters, schemas.DetailedIntegritySchema):
    class Meta(schemas.DetailedIntegritySchema.Meta):
        pass


class PatchIntegrityDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    PATH_CHOICES = tuple('/%s' % field for field in (Integrity.title.key,))
