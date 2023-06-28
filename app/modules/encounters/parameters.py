# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Encounters resources RESTful API
-----------------------------------------------------------
"""
import logging

from flask_login import current_user

import app.modules.utils as util
from app.modules.users.permissions import rules
from app.utils import HoustonException
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas

log = logging.getLogger(__name__)


class CreateEncounterParameters(Parameters, schemas.DetailedEncounterSchema):
    class Meta(schemas.DetailedEncounterSchema.Meta):
        pass


class PatchEncounterDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring

    # Valid options for patching are replace '/owner'
    PATH_CHOICES = (
        '/owner',
        '/annotations',
        '/time',
        '/timeSpecificity',
        '/customFields',
        '/decimalLatitude',
        '/decimalLongitude',
        '/locationId',
        '/sex',
        '/taxonomy',
        '/verbatimLocality',
    )

    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    # equivalent to replace for all our targets
    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        from app.modules.complex_date_time.models import ComplexDateTime
        from app.modules.users.models import User

        from .models import db

        ret_val = False
        if field == 'owner':
            # owner is permitted to assign ownership to another researcher
            user = User.query.get(value)
            if (
                rules.owner_or_privileged(current_user, obj)
                and user
                and user.is_researcher
            ):
                obj.owner = user
                ret_val = True
        elif field == 'annotations':
            from app.modules.annotations.models import Annotation

            # can assign annotations (in patch only) but they must be valid
            annot = Annotation.query.get(value)
            if not annot:
                raise HoustonException(
                    log, f'guid value passed ({value}) is not an annotation guid'
                )
            if annot.encounter and not annot.encounter.current_user_has_edit_permission():
                raise HoustonException(
                    log, f'annotation {value} owned by a different user', obj=annot
                )
            annot.encounter = obj

            with db.session.begin(subtransactions=True):
                db.session.merge(annot)
            ret_val = True

        elif field == 'time' or field == 'timeSpecificity':
            ret_val = ComplexDateTime.patch_replace_helper(obj, field, value)

        elif field == 'customFields':
            # taken directly from edm code:
            #   passed can take two formats:
            #   - { "id": "cfdId", "value": "some value" }
            #   - { "cfdId0": "value0", ..., "cfdIdN": "valueN" }
            # possible backstory: DEX-753
            assert isinstance(value, dict), 'customFields must be passed a json object'
            if value.get('id'):
                assert 'value' in value, 'customFields id/value format needs both'
                value = {value['id']: value['value']}
            obj.set_custom_field_values_json(value)  # does all the validation etc
            ret_val = True
        elif field == 'decimalLatitude':
            if value is not None and not util.is_valid_latitude(value):
                raise HoustonException(
                    log, f'decimalLatitude value passed ({value}) is invalid'
                )
            obj.decimal_latitude = value
            ret_val = True
        elif field == 'decimalLongitude':
            if value is not None and not util.is_valid_longitude(value):
                raise HoustonException(
                    log, f'decimalLongitude value passed ({value}) is invalid'
                )
            obj.decimal_longitude = value
            ret_val = True
        elif field == 'locationId':
            if value is not None and not util.is_valid_uuid_string(value):
                raise HoustonException(
                    log, f'locationId value passed ({value}) is not a guid'
                )
            obj.location_guid = value
            ret_val = True
        elif field == 'verbatimLocality':
            obj.verbatim_locality = value
            ret_val = True
        elif field == 'taxonomy':
            if value is not None and not util.is_valid_uuid_string(value):
                raise HoustonException(
                    log, f'taxonomy value passed ({value}) is not a guid'
                )
            obj.taxonomy_guid = value
            ret_val = True
        elif field == 'sex':
            if value is not None and not util.is_valid_sex(value):
                raise HoustonException(log, f'invalid sex value passed ({value})')
            obj.sex = value
            ret_val = True
        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        from app.modules.complex_date_time.models import ComplexDateTime

        ret_val = False

        # remove one of these, it will remove both
        if (field == 'time' or field == 'timeSpecificity') and obj.time_guid:
            cdt = ComplexDateTime.query.get(obj.time_guid)
            if not cdt:
                return False
            from .models import db

            log.debug(f'patch removing {cdt} from {obj}')
            obj.time_guid = None
            with db.session.begin(subtransactions=True):
                db.session.delete(cdt)
            ret_val = True

        return ret_val
