# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Social Groups resources RESTful API
-----------------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import SocialGroup


class CreateSocialGroupParameters(Parameters, schemas.DetailedSocialGroupSchema):
    name = base_fields.String(description='The name of the social group', required=True)
    members = base_fields.List(base_fields.Dict, required=True)

    class Meta(schemas.DetailedSocialGroupSchema.Meta):
        pass


class PatchSocialGroupDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    PATH_CHOICES = tuple('/%s' % field for field in (SocialGroup.name.key,))
