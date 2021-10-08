# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Relationships resources RESTful API
-----------------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import Relationship


class CreateRelationshipParameters(Parameters, schemas.DetailedRelationshipSchema):

    class Meta(schemas.DetailedRelationshipSchema.Meta):
        pass


class PatchRelationshipDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
    )

    PATH_CHOICES = tuple(
        '/%s' % field for field in (
            Relationship.start_date.key,
            Relationship.end_date.key
        )
    )