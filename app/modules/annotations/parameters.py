# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Annotations resources RESTful API
-----------------------------------------------------------
"""
from flask_marshmallow import base_fields
from flask_restx_patched import Parameters, PatchJSONParameters
from flask_login import current_user
from app.modules.users.permissions import rules
from . import schemas
from .models import Annotation


class CreateAnnotationParameters(Parameters, schemas.DetailedAnnotationSchema):
    asset_guid = base_fields.UUID(description='The GUID of the asset', required=True)
    encounter_guid = base_fields.UUID(
        description='The GUID of the encounter',
        required=False,
    )

    class Meta(schemas.DetailedAnnotationSchema.Meta):
        pass


class PatchAnnotationDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES = tuple(
        '/%s' % field
        for field in (
            'encounter_guid',
            'keywords',
        )
    )

    @classmethod
    def add(cls, obj, field, value, state):
        if field == 'keywords':
            from app.modules.keywords.models import Keyword

            if isinstance(value, dict):  # (possible) new keyword
                keyword = obj.add_new_keyword(
                    value.get('value', None), value.get('source', None)
                )
                if keyword is None:
                    return False
            else:
                keyword = Keyword.query.get(value)
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
        # Annotations don't have an owner, so check the encounter owner
        if (
            rules.owner_or_privileged(current_user, obj.encounter)
            or current_user.is_admin
        ):
            if field == Annotation.encounter_guid.key:
                encounter = Encounter.query.get(value)
                if encounter and rules.owner_or_privileged(current_user, encounter):
                    obj.encounter_guid = value
                    ret_val = True

        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        if field == 'keywords':
            from app.modules.keywords.models import Keyword

            keyword = Keyword.query.get(value)
            if keyword is None:
                return False
            obj.remove_keyword(keyword)
            return True
        return False
