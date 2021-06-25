# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Individuals resources RESTful API
-----------------------------------------------------------
"""
from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas
from app.modules.users.permissions import rules
from app.modules.users.permissions.types import AccessOperation
import logging
import uuid


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def is_valid_uuid(query_id):
    try:
        uuid.UUID(str(query_id))
        return True
    except ValueError:
        return False


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

    # Is this weird? I need to modify EDM and Houston records
    PATH_CHOICES_HOUSTON = ['encounters']

    PATH_CHOICES_EDM = ['encounters']

    PATH_CHOICES = tuple(
        '/%s' % field for field in (PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON)
    )

    @classmethod
    def remove(cls, obj, field, value, state):
        has_permission = rules.ObjectActionRule(obj, AccessOperation.WRITE).check()
        ret_val = False
        if has_permission:
            if field == 'encounters':
                for encounter_guid in value:
                    if is_valid_uuid(encounter_guid):
                        from app.modules.encounters.models import Encounter

                        encounter = Encounter.query.filter(
                            Encounter.guid == encounter_guid
                        ).first()
                        if encounter is not None and encounter in obj.encounters:
                            obj.remove_encounter(encounter)
                            ret_val = True
            else:
                super(PatchIndividualDetailsParameters, cls).replace(
                    obj, field, value, state
                )
        return ret_val

    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):

        ret_val = False
        has_permission = rules.ObjectActionRule(obj, AccessOperation.WRITE).check()
        if has_permission:
            if field == 'encounters':
                for encounter_guid in value:
                    if is_valid_uuid(encounter_guid):
                        from app.modules.encounters.models import Encounter

                        encounter = Encounter.query.filter(
                            Encounter.guid == encounter_guid
                        ).first()
                        if encounter is not None and encounter not in obj.encounters:
                            obj.add_encounter(encounter)
                            assert encounter in obj.get_encounters()
                            ret_val = True
            else:
                super(PatchIndividualDetailsParameters, cls).replace(
                    obj, field, value, state
                )
        return ret_val
