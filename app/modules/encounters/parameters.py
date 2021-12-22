# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Encounters resources RESTful API
-----------------------------------------------------------
"""

from flask_login import current_user
from flask_restx_patched import Parameters, PatchJSONParametersWithPassword
from . import schemas
from app.modules.users.permissions import rules
import logging

log = logging.getLogger(__name__)


class CreateEncounterParameters(Parameters, schemas.DetailedEncounterSchema):
    class Meta(schemas.DetailedEncounterSchema.Meta):
        pass


class PatchEncounterDetailsParameters(PatchJSONParametersWithPassword):
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
        '/current_password',
        '/user',
        '/owner',
        '/time',
        '/timeSpecificity',
    )

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

    # equivalent to replace for all our targets
    @classmethod
    def add(cls, obj, field, value, state):
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        from app.modules.users.models import User
        from app.modules.complex_date_time.models import ComplexDateTime, Specificities
        from datetime import datetime
        from app.utils import normalized_timezone_string
        from .models import db

        super(PatchEncounterDetailsParameters, cls).replace(obj, field, value, state)
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

        # * note: requires `value` is iso8601 **with timezone**
        # this gets a little funky in the event there is *no existing time set* as the patch
        #   happens in two parts that know nothing about each other.  so we have to create a ComplexDateTime and
        #   *fake* the other field value (time/timeSpecificity) upon doing so.  :(  we then hope that the subsequent
        #   patch for the other field is coming down the pipe.  api user beware!
        # note: the dict-based all-at-once solution below is the better choice if you can swing it.
        elif (field == 'time' or field == 'timeSpecificity') and isinstance(value, str):
            dt = None
            specificity = None
            timezone = None
            if field == 'time':
                # this will throw ValueError if not parseable
                dt = datetime.fromisoformat(value)
                if not dt.tzinfo:
                    raise ValueError(f'passed value {value} does not have time zone data')
                timezone = normalized_timezone_string(dt)
                log.debug(f'patch field={field} value => {dt} + {timezone}')
            else:
                if not Specificities.has_value(value):
                    raise ValueError(f'invalid specificity: {value}')
                specificity = Specificities[value]
                log.debug(f'patch field={field} value => {specificity}')
            time_cfd = obj.time
            if time_cfd:  # we just update it
                if specificity:
                    time_cfd.specificity = specificity
                    log.debug(f'patch updated specificity on {time_cfd}')
                else:
                    time_cfd.datetime = dt
                    time_cfd.timezone = timezone
                    log.debug(f'patch updated datetime+timezone on {time_cfd}')
                ret_val = True
            else:
                # this is the wonky bit - we have to create ComplexDateTime based only one of datetime/specificity
                if not dt:
                    dt = datetime.utcnow()
                    timezone = 'UTC'
                if not specificity:
                    specificity = Specificities.time
                log.warning(
                    f'patch field={field} given single value and has no current ComplexDateTime, generating new one with ({dt}, {timezone}, {specificity})'
                )
                time_cfd = ComplexDateTime(dt, timezone, specificity)
                with db.session.begin(subtransactions=True):
                    db.session.add(time_cfd)
                obj.time = time_cfd
                obj.time_guid = time_cfd.guid
                ret_val = True

        # this takes a dict and uses for ComplexDateTime creation.  dict can be one of:
        #  - { time: iso8601, specificity: y }   (timezone derived from iso8601)
        #  - { time: iso8601, timeZone: tz, specificity: y }   (timezone explicit, not from time value)
        elif field == 'time' and isinstance(value, dict):
            raise ValueError('not yet implemented')  # FIXME
            ret_val = False

        return ret_val

    @classmethod
    def remove(cls, obj, field, value, state):
        from app.modules.complex_date_time.models import ComplexDateTime

        super(PatchEncounterDetailsParameters, cls).remove(obj, field, value, state)
        ret_val = False

        # remove one of these, it will remove both
        if (field == 'time' or field == 'timeSpecificity') and obj.time_guid:
            cdt = ComplexDateTime.query.get(obj.time_guid)
            if not cdt:
                return False
            from .models import db

            obj.time_guid = None
            with db.session.begin():
                db.session.delete(cdt)
            ret_val = True

        return ret_val
