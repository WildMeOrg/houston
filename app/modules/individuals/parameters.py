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

    VALID_FIELDS = ['encounters']
    PATH_CHOICES = tuple('/%s' % field for field in (VALID_FIELDS))

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
                        if encounter is not None and encounter not in obj.encounters:
                            obj.remove_encounter(encounter)
                            ret_val = True
        return ret_val

    @classmethod
    def add(cls, obj, field, value, state):
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
                        if encounter is not None and encounter not in obj.encounters:
                            obj.add_encounter(encounter)
                            ret_val = True
        return ret_val

    @classmethod
    def replace(cls, obj, field, value, state):
        has_permission = rules.ObjectActionRule(obj, AccessOperation.WRITE).check()
        ret_val = False
        if has_permission:
            super(PatchIndividualDetailsParameters, cls).replace(obj, field, value, state)
            ret_val = True
        return ret_val
