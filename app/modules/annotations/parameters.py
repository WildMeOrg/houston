# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Annotations resources RESTful API
-----------------------------------------------------------
"""

from http import HTTPStatus

from flask_login import current_user

from app.extensions.api import abort
from app.modules.users.permissions import rules
from flask_restx_patched import PatchJSONParameters

from .models import Annotation


class PatchAnnotationDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_TEST,
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    @classmethod
    def _check_keyword_value(cls, obj, field, value, state, create=True):
        from app.modules.keywords.models import Keyword

        keyword = None

        # Keywords can be pulled from previous test ops using the array indexing (i.e., "[0]") signature
        if isinstance(value, str):
            if value[0] == '[' and value[-1] == ']':
                index = value[1:-1]
                if index.isnumeric():
                    index = int(index)
                    keywords = state.get(field, [])
                    try:
                        keyword = keywords[index]
                    except Exception:
                        pass

        # Otherwise, try to ensure the keyword as normal
        if keyword is None:
            keyword = Keyword.ensure_keyword(value, create=create)

        return keyword

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
        if field == 'keywords':
            keyword = cls._check_keyword_value(obj, field, value, state)
            assert keyword is not None, 'Keyword creation failed'

            if field not in state:
                state[field] = []
            state[field].append(keyword)

            return True

        return super(PatchAnnotationDetailsParameters, cls).test(obj, field, value, state)

    @classmethod
    def add(cls, obj, field, value, state):
        if field == 'keywords':
            keyword = cls._check_keyword_value(obj, field, value, state, create=False)

            if keyword is None:
                return False

            obj.add_keyword(keyword)
            return True

        # otherwise, add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False
        if (
            rules.owner_or_privileged(current_user, obj.asset.git_store)
            or current_user.is_admin
        ):
            if field == Annotation.bounds.key:
                try:
                    Annotation.validate_bounds(value)
                except Exception:
                    abort(
                        code=HTTPStatus.UNPROCESSABLE_ENTITY,
                        message='bounds value is invalid',
                    )
            ret_val = super(PatchAnnotationDetailsParameters, cls).replace(
                obj, field, value, state
            )
            if field == Annotation.bounds.key or field == Annotation.ia_class.key:
                # Setting of these fields means that the Sage annotation must be recalculated
                obj.content_guid = None

        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        if field == 'keywords':
            keyword = cls._check_keyword_value(obj, field, value, state, create=False)

            if keyword is not None:
                obj.remove_keyword(keyword)
                keyword.delete_if_unreferenced()

            return True

        return False
