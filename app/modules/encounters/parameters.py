# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Encounters resources RESTful API
-----------------------------------------------------------
"""
from flask_login import current_user
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas
from app.modules.users.permissions import rules
import logging


from app.utils import HoustonException

log = logging.getLogger(__name__)


class CreateEncounterParameters(Parameters, schemas.DetailedEncounterSchema):
    class Meta(schemas.DetailedEncounterSchema.Meta):
        pass


class PatchEncounterDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring

    PATH_CHOICES_EDM = (
        '/comments',
        '/customFields',
        '/decimalLatitude',
        '/decimalLongitude',
        '/locationId',
        '/sex',
        '/taxonomy',
        '/verbatimLocality',
    )

    # Valid options for patching are replace '/owner'
    PATH_CHOICES_HOUSTON = (
        '/owner',
        '/annotations',
        '/time',
        '/timeSpecificity',
    )

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

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
        from app.modules.users.models import User
        from app.modules.complex_date_time.models import ComplexDateTime
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
                    log, f'annotation {value} owned by a different user'
                )
            annot.encounter = obj

            with db.session.begin(subtransactions=True):
                db.session.merge(annot)
            ret_val = True

        elif field == 'time' or field == 'timeSpecificity':
            ret_val = ComplexDateTime.patch_replace_helper(obj, field, value)

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
