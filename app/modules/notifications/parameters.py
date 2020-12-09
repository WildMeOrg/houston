# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Notifications resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields
# from flask_restplus_patched import Parameters, PatchJSONParameters
from flask_restplus_patched import Parameters

from . import schemas
from .models import Notification  # NOQA


class CreateNotificationParameters(Parameters, schemas.DetailedNotificationSchema):
    class Meta(schemas.DetailedNotificationSchema.Meta):
        pass
