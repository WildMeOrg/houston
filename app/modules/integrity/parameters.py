# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Integrity resources RESTful API
-----------------------------------------------------------
"""

from flask_restx_patched import Parameters

from . import schemas


class CreateIntegrityParameters(Parameters, schemas.BaseIntegritySchema):
    class Meta(schemas.BaseIntegritySchema.Meta):
        pass
