# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Individuals resources RESTful API
-----------------------------------------------------------
"""

from flask_restplus_patched import Parameters, PatchJSONParameters

from . import schemas


class CreateIndividualParameters(Parameters, schemas.DetailedIndividualSchema):
    class Meta(schemas.DetailedIndividualSchema.Meta):
        pass


class PatchIndividualDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    VALID_FIELDS = ['encounters']
    PATH_CHOICES = tuple('/%s' % field for field in (VALID_FIELDS))
