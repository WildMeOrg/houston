# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Annotations resources RESTful API
-----------------------------------------------------------
"""

from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas


class CreateAnnotationParameters(Parameters, schemas.DetailedAnnotationSchema):
    class Meta(schemas.DetailedAnnotationSchema.Meta):
        pass


class PatchAnnotationDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    PATH_CHOICES = tuple('/%s' % field for field in ('NowtYet',))
