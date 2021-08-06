# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Collaborations resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters
from flask_marshmallow import base_fields

from . import schemas
from .models import Collaboration


class CreateCollaborationParameters(Parameters, schemas.DetailedCollaborationSchema):
    user_guid = base_fields.UUID(
        description='The GUID of the other user',
        required=True,
    )
    # This is used for when a user manager is creating a collaboration between two different users.
    second_user_guid = base_fields.UUID(
        description='The GUID of the second user',
        required=False,
    )
    title = base_fields.String(required=False)

    class Meta(schemas.DetailedCollaborationSchema.Meta):
        pass


class PatchCollaborationDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    PATH_CHOICES = tuple('/%s' % field for field in (Collaboration.title.key,))
