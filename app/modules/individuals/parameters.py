# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Individuals resources RESTful API
-----------------------------------------------------------
"""
from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas
import logging
import uuid

from .models import Individual

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
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE,)

    VALID_FIELDS = ['encounters']
    PATH_CHOICES = tuple('/%s' % field for field in (VALID_FIELDS))

    @classmethod
    def replace(cls, obj, field, value, state):
        ret_val = False
        if field == 'encounters':
            if len(value) == 0:
                ret_val = True
            encounter_list = []
            for encounter_guid in value:
                if is_valid_uuid(encounter_guid):
                    from app.modules.encounters.models import Encounter

                    encounter = Encounter.query.filter(
                        Encounter.guid == encounter_guid
                    ).first()
                    if encounter is not None and encounter not in encounter_list:
                        encounter_list.append(encounter)
                    ret_val = True
            obj.encounters = encounter_list
        if ret_val is False:
            super(PatchIndividualDetailsParameters, cls).replace(obj, field, value, state)
        return ret_val
