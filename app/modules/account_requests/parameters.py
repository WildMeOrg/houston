# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for AccountRequest resources RESTful API
-----------------------------------------------------------
"""

from flask_restx_patched import Parameters

from . import schemas


class CreateAccountRequestParameters(Parameters, schemas.BaseAccountRequestSchema):
    class Meta(schemas.BaseAccountRequestSchema.Meta):
        pass
