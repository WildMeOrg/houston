# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Sightings resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import Sighting


class CreateSightingParameters(Parameters, schemas.DetailedSightingSchema):
    class Meta(schemas.DetailedSightingSchema.Meta):
        pass


class PatchSightingDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    PATH_CHOICES_EDM = ('/locationId',)
    PATH_CHOICES = (
        tuple('/%s' % field for field in (Sighting.guid.key,)) + PATH_CHOICES_EDM
    )
