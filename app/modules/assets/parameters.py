# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Assets resources RESTful API
-------------------------------------------------------------
"""

from flask_restx_patched import PatchJSONParameters
from flask_restx_patched._http import HTTPStatus
from app.extensions.api import abort

from . import schemas


class PatchAssetParameters(PatchJSONParameters):
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    PATH_CHOICES = ('/image',)

    @classmethod
    def replace(cls, obj, field, value, state):
        ret_val = False

        if field == 'image':
            schema = schemas.PatchAssetSchema()
            errors = schema.validate(value)
            if errors:
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=schema.get_error_message(errors),
                )
            obj.rotate(value['rotate']['angle'])
            ret_val = True

        return ret_val
