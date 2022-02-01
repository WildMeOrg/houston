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
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES = tuple('/%s' % field for field in ('tags', 'image'))

    @classmethod
    def add(cls, obj, field, value, state):
        if field == 'tags':
            from app.modules.keywords.models import Keyword as Tag

            if isinstance(value, dict):  # (possible) new tag
                tag = obj.add_new_tag(value.get('value', None), value.get('source', None))
                if tag is None:
                    return False
            else:
                tag = Tag.query.get(value)
                if tag is None:
                    return False
                obj.add_tag(tag)
            return True

        # otherwise, add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

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

    @classmethod
    def remove(cls, obj, field, value, state):
        if field == 'tags':
            from app.modules.keywords.models import Keyword as Tag

            tag = Tag.query.get(value)
            if tag is None:
                return False
            obj.remove_tag(tag)
            tag.delete_if_unreferenced()
            return True
        return False
