# -*- coding: utf-8 -*-
"""
Serialization schemas for Configuration resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema


class BaseConfigurationSchema(ModelSchema):
    """
    Base Configuration schema exposes only the most general fields.
    """

    edm_target = base_fields.String(required=True)
