# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Sightings resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas


class CreateSightingParameters(Parameters, schemas.DetailedSightingSchema):
    class Meta(schemas.DetailedSightingSchema.Meta):
        pass


class PatchSightingDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES_EDM = (
        '/locationId',
        '/startTime',
        '/endTime',
    )
    PATH_CHOICES = (
        PATH_CHOICES_EDM  # for now, no patching on houston sighting needed/supported
    )
