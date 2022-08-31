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
from .models import Annotation, ScoutAnnotation


class CreateAnnotationParameters(Parameters, schemas.BaseAnnotationSchema):
    asset_guid = base_fields.UUID(description='The GUID of the asset', required=True)
    task_guid = base_fields.UUID(
        description='The GUID of the task',
        required=True,
    )

    class Meta(schemas.BaseAnnotationSchema.Meta):
        fields = schemas.BaseAnnotationSchema.Meta.fields + (
            Annotation.ia_class.key,
            Annotation.bounds.key,
            ScoutAnnotation.task_guid.key,
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
            'ia_class',
            'bounds',
        )
    )

    NON_NULL_PATHS = ('/ia_class',)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False
        # Annotations don't have an owner and encounter are (briefly) optional, so we check asset(_group)
        #  future consideration: first check encounter (IF exists), fallback to asset(_group)
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
        # Nothing can be removed, Keywords not yet supported on Scout Annots but may potentially be in the
        # future

        return False
