# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Individuals resources RESTful API
-----------------------------------------------------------
"""
from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas
import logging


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

    PATH_CHOICES_EDM = ('/encounters',)

    PATH_CHOICES = PATH_CHOICES_EDM

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
        return ret_val

    @classmethod
    def add(cls, obj, field, value, state):
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
        return ret_val
