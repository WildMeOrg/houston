# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Annotations resources RESTful API
-----------------------------------------------------------
"""
from http import HTTPStatus

from flask_login import current_user
from flask_marshmallow import base_fields
from marshmallow import validates_schema

from app.extensions.api import abort
from app.modules.annotations.parameters import (
    PatchAnnotationDetailsParameters as BasePatchAnnotationDetailsParameters,
)
from app.modules.users.permissions import rules
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from .models import Annotation, CodexAnnotation


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


class PatchAnnotationDetailsParameters(BasePatchAnnotationDetailsParameters):
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
            if field == CodexAnnotation.encounter_guid.key:
                encounter = Encounter.query.get(value)
                if (
                    encounter
                    and rules.owner_or_privileged(current_user, encounter)
                    and obj.encounter.sighting == encounter.sighting
                ):
                    obj.encounter_guid = value
                    ret_val = True
            else:  # any other field
                ret_val = super(PatchAnnotationDetailsParameters, cls).replace(
                    obj, field, value, state
                )

        return ret_val
