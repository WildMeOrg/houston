# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Individuals resources RESTful API
-----------------------------------------------------------
"""
from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas
import logging
import app.modules.utils as util
from flask_restx_patched._http import HTTPStatus
from app.extensions.api import abort
from uuid import UUID


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class CreateIndividualParameters(Parameters, schemas.DetailedIndividualSchema):
    class Meta(schemas.DetailedIndividualSchema.Meta):
        pass


class PatchIndividualDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES_EDM = (
        '/encounters',
        '/sex',
        '/timeOfBirth',
        '/timeOfDeath',
        '/comments',
        '/names',
    )

    PATH_CHOICES_HOUSTON = ('/featuredAssetGuid', '/encounters', '/names')

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

    @classmethod
    def remove(cls, obj, field, value, state):
        ret_val = False
        if field == 'encounters':
            for encounter_guid in value:
                from app.modules.encounters.models import Encounter

                encounter = Encounter.query.get(encounter_guid)
                if encounter is not None and encounter in obj.encounters:
                    obj.remove_encounter(encounter)
                    ret_val = True
        elif field == 'featuredAssetGuid' and util.is_valid_guid(value):
            obj.set_featured_asset_guid(UUID(value, version=4))
            ret_val = True
        elif field == 'names' and util.is_valid_guid(value):
            from app.modules.names.models import Name

            name = Name.query.get(value)
            if not name or name.individual_guid != obj.guid:
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f'invalid name guid {value}',
                )
            removed = obj.remove_name(name)
            if not removed:
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f'{name} could not be removed from {obj}',
                )
            ret_val = True

        return ret_val

    @classmethod
    def add(cls, obj, field, value, state):
        if field == 'names':  # add and replace are diff for names
            if not isinstance(value, dict) or set(value.keys()) != set(
                ['context'], ['value']
            ):
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message='value must contain keys "context" and "value"',
                )
            from flask_login import current_user

            obj.add_name(value['context'], value['value'], current_user)
            return True

        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        ret_val = False
        if field == 'encounters':
            for encounter_guid in value:
                from app.modules.encounters.models import Encounter

                encounter = Encounter.query.get(encounter_guid)
                if encounter is not None and encounter not in obj.encounters:
                    obj.add_encounter(encounter)
                    assert encounter in obj.get_encounters()
                    ret_val = True
        elif field == 'featuredAssetGuid' and util.is_valid_guid(value):
            obj.set_featured_asset_guid(UUID(value, version=4))
            ret_val = True
        elif field == 'names':
            from app.modules.names.models import Name

            if (
                not isinstance(value, dict)
                or set(value.keys()) != set(['guid'], ['context'], ['value'])
                or not util.is_valid_guid(value['guid'])
            ):
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message='value must contain keys "guid", "context", and "value"',
                )
            name = Name.query.get(value['guid'])
            if not name or name.individual_guid != obj.guid:
                abort(
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f"invalid name guid {value['guid']}",
                )
            name.context = value['context']
            name.value = value['value']
            ret_val = True

        return ret_val
