# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Assets resources RESTful API
-------------------------------------------------------------
"""

from http import HTTPStatus

from app.extensions.api import abort
from flask_restx_patched import PatchJSONParameters

from . import schemas


class PatchAssetParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_TEST,
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES = tuple('/%s' % field for field in ('tags', 'image'))

    @classmethod
    def _check_tag_value(cls, obj, field, value, state, create=True):
        from app.modules.keywords.models import Keyword as Tag

        tag = None

        # Tags can be pulled from previous test ops using the array indexing (i.e., "[0]") signature
        if isinstance(value, str):
            if value[0] == '[' and value[-1] == ']':
                index = value[1:-1]
                if index.isnumeric():
                    index = int(index)
                    tags = state.get(field, [])
                    try:
                        tag = tags[index]
                    except Exception:
                        pass

        # Otherwise, try to ensure the tag as normal
        if tag is None:
            tag = Tag.ensure_keyword(value, create=create)

        return tag

    @classmethod
    def test(cls, obj, field, value, state):
        """
        This is method for test operation. It is separated to provide a
        possibility to easily override it in your Parameters.

        Args:
            obj (object): an instance to change.
            field (str): field name
            value (str): new value
            state (dict): inter-operations state storage

        Returns:
            processing_status (bool): True
        """
        if field == 'tags':
            tag = cls._check_tag_value(obj, field, value, state)
            assert tag is not None, 'Tag creation failed'

            if field not in state:
                state[field] = []
            state[field].append(tag)

            return True

        return super(PatchAssetParameters, cls).test(obj, field, value, state)

    @classmethod
    def add(cls, obj, field, value, state):
        if field == 'tags':
            tag = cls._check_tag_value(obj, field, value, state, create=False)

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
            tag = cls._check_tag_value(obj, field, value, state, create=False)

            if tag is not None:
                obj.remove_tag(tag)
                tag.delete_if_unreferenced()

            return True

        return False
