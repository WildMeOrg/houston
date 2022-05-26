# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Annotations resources RESTful API
-----------------------------------------------------------
"""
from flask_login import current_user
from flask_marshmallow import base_fields
from marshmallow import validates_schema

from app.extensions.api import abort
from app.modules.users.permissions import rules
from flask_restx_patched import Parameters, PatchJSONParameters
from flask_restx_patched._http import HTTPStatus

from . import schemas
from .models import Annotation


class CreateAnnotationParameters(Parameters, schemas.BaseAnnotationSchema):
    asset_guid = base_fields.UUID(description='The GUID of the asset', required=True)
    encounter_guid = base_fields.UUID(
        description='The GUID of the encounter',
        required=False,
    )

    class Meta(schemas.BaseAnnotationSchema.Meta):
        fields = schemas.BaseAnnotationSchema.Meta.fields + (
            Annotation.ia_class.key,
            Annotation.bounds.key,
        )

    @validates_schema
    def validate_bounds(self, data):
        try:
            Annotation.validate_bounds(data.get('bounds'))
        except Exception:
            abort(code=HTTPStatus.UNPROCESSABLE_ENTITY, message='bounds value is invalid')


class PatchAnnotationDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_TEST,
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES = tuple(
        '/%s' % field
        for field in (
            'encounter_guid',
            'ia_class',
            'bounds',
            'keywords',
        )
    )

    NON_NULL_PATHS = ('/ia_class',)

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
        from app.modules.encounters.models import Encounter

        ret_val = False
        # Annotations don't have an owner and encounter are (briefly) optional, so we check asset(_group)
        #  future consideration: first check encounter (IF exists), fallback to asset(_group)
        if (
            rules.owner_or_privileged(current_user, obj.asset.git_store)
            or current_user.is_admin
        ):
            # only can assign encounter if have privileges there and the sighting doesn't change
            if field == Annotation.encounter_guid.key:
                encounter = Encounter.query.get(value)
                if (
                    encounter
                    and rules.owner_or_privileged(current_user, encounter)
                    and obj.encounter.sighting == encounter.sighting
                ):
                    obj.encounter_guid = value
                    ret_val = True
            else:  # any other field
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
