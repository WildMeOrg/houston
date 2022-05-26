# -*- coding: utf-8 -*-
"""
ComplexDateTime database models
A structure for holding a DateTime object with additional complexity
involving time zone and specificity
--------------------
"""
import datetime
import enum
import logging
import uuid

import pytz
from dateutil import tz

import app.extensions.logging as AuditLog
from app.extensions import db
from app.utils import normalized_timezone_string

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Specificities(str, enum.Enum):
    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_

    year = 'year'
    month = 'month'
    day = 'day'
    time = 'time'


class ComplexDateTime(db.Model):
    """
    ComplexDateTime database model.
    * Date + Time (utc)
    * Time Zone (where time observed)
    * Specificity:  how precise is the date/time?  year/month/day/time
    """

    def __init__(self, dt, timezone, specificity, *args, **kwargs):
        if not dt or not isinstance(dt, datetime.datetime):
            raise ValueError('must pass a datetime object')
        if not timezone:
            raise ValueError('must provide a time zone')
        if not tz.gettz(timezone):
            raise ValueError(f'unrecognized time zone {timezone}')
        if not isinstance(specificity, Specificities) or specificity not in Specificities:
            raise ValueError(f'invalid specificity {specificity}')
        super().__init__(*args, **kwargs)
        self.datetime = dt.astimezone(pytz.UTC)
        self.timezone = timezone
        self.specificity = specificity

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    datetime = db.Column(
        db.DateTime, index=True, default=datetime.datetime.utcnow, nullable=False
    )

    timezone = db.Column(db.String(), index=True, nullable=False, default='Z')

    specificity = db.Column(db.Enum(Specificities), index=True, nullable=False)

    # will throw ValueError for various problems, including via datetime constructor (based on values)
    @classmethod
    def from_list(cls, parts, timezone, specificity=None):
        if not parts or not isinstance(parts, list):
            raise ValueError('must pass list of datetime components (with at least year)')
        if not timezone:
            raise ValueError('must provide a time zone')
        if not tz.gettz(timezone):
            raise ValueError(f'unrecognized time zone {timezone}')
        if specificity and (
            not isinstance(specificity, Specificities) or specificity not in Specificities
        ):
            raise ValueError(f'invalid specificity {specificity}')

        # now we ascertain specificity if we dont have it
        if not specificity:
            if len(parts) == 1:
                specificity = Specificities.year
            elif len(parts) == 2:
                specificity = Specificities.month
            elif len(parts) == 3:
                specificity = Specificities.day
            else:
                specificity = Specificities.time

        # now we pad out parts (dont need to do hour/min/sec as they have defaults of 0 in constructor)
        if len(parts) == 1:
            parts.append(1)  # add january
        if len(parts) == 2:
            parts.append(1)  # add 1st of month
        # will throw ValueError if bunk data passed in
        dt = datetime.datetime(*parts, tzinfo=tz.gettz(timezone))
        return ComplexDateTime(dt, timezone, specificity)

    # this accepts a dict which is roughly "user input".  it will look for a mix of items passed in,
    #   but requires `time` to be one of them.   valid combinations include:
    #   1. time, timeSpecificity - time is iso8601 and must have timezone
    #   2. time = {datetime:, timezone:, specificity:} - timezone optional here iff included in datetime iso8601
    #   3. time = {components: [], timezone:, specificity:} - components = [Y, M, D, h, m, s]; specificity is optional
    #  note: heavy-lifting really done by from_dict() below
    @classmethod
    def from_data(cls, data):
        if not data or not isinstance(data, dict) or 'time' not in data:
            AuditLog.frontend_fault(
                log, f'invalid data for ComplexDateTime.from_data(): {data}'
            )
            raise ValueError(f'invalid data: {data}')
        time_data = data['time']
        if isinstance(time_data, str):
            time_data = {
                'datetime': data['time'],
                'specificity': data.get('timeSpecificity'),
            }
        elif not isinstance(time_data, dict):
            AuditLog.frontend_fault(
                log, f'invalid data type for ComplexDateTime.from_data(): {time_data}'
            )
            raise ValueError(f'invalid data: {time_data}')
        return cls.from_dict(time_data)

    # see notes above; this only wants a dict passed in
    @classmethod
    def from_dict(cls, data):
        if not data or not isinstance(data, dict):
            AuditLog.frontend_fault(
                log, f'invalid data for ComplexDateTime.from_dict(): {data}'
            )
            raise ValueError(f'time parsing error, invalid data: {data}')
        if 'components' in data:
            if not isinstance(data['components'], list):
                AuditLog.frontend_fault(
                    log,
                    f'components element not a list in ComplexDateTime.from_dict(): {data}',
                )
                raise ValueError('time parsing error, components must be a list')
            return cls.from_list(
                data['components'], data.get('timezone'), data.get('specificity')
            )
        dt_str = data.get('datetime')
        if not dt_str:
            AuditLog.frontend_fault(
                log, f'no datetime for ComplexDateTime.from_dict(): {data}'
            )
            raise ValueError('time parsing error, missing datetime value')
        dt = datetime.datetime.fromisoformat(dt_str)  # will throw ValueError if invalid
        timezone = data.get('timezone')
        if not timezone:  # hope we can get one from datetime
            if not dt.tzinfo:
                AuditLog.frontend_fault(
                    log,
                    f'no timezone in data and cannot be derived from datetime: {data}',
                )
                raise ValueError(
                    f'time parsing error, timezone not passed and cannot be derived from {dt_str}'
                )
            timezone = normalized_timezone_string(dt)
        spec_str = data.get('specificity')
        if not spec_str or not Specificities.has_value(spec_str):
            AuditLog.frontend_fault(log, f'no/invalid specificity: {data}')
            raise ValueError('time parsing error, invalid specificity')
        specificity = Specificities[spec_str]
        return ComplexDateTime(dt, timezone, specificity)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'datetime={self.datetime}, '
            'timezone={self.timezone}, '
            'specificity={self.specificity} '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    # returns actual timezone object
    def get_timezone_object(self):
        return tz.gettz(self.timezone)

    def get_datetime_in_timezone(self):
        return self.datetime.astimezone(self.get_timezone_object())

    def get_timezone_normalized(self):
        return normalized_timezone_string(self.get_datetime_in_timezone())

    def isoformat_utc(self):
        return self.datetime.isoformat()

    def isoformat_in_timezone(self):
        return self.get_datetime_in_timezone().isoformat()

    # used from parameters.py for object which have time/timeSpecifity patches (currently encounter and sighting)
    @classmethod
    def patch_replace_helper(cls, obj, field, value):
        import pytz

        from app.modules.complex_date_time.models import ComplexDateTime, Specificities
        from app.utils import normalized_timezone_string

        from .models import db

        # * note: field==time requires `value` is iso8601 **with timezone**
        # this gets a little funky in the event there is *no existing time set* as the patch
        #   happens in two parts that know nothing about each other.  so we have to create a ComplexDateTime and
        #   *fake* the other field value (time/timeSpecificity) upon doing so.  :(  we then hope that the subsequent
        #   patch for the other field is coming down the pipe.  api user beware!
        # note: the dict-based all-at-once solution below is the better choice if you can swing it.

        if (field == 'time' or field == 'timeSpecificity') and isinstance(value, str):
            dt = None
            specificity = None
            timezone = None
            if field == 'time':
                # this will throw ValueError if not parseable
                dt = datetime.datetime.fromisoformat(value)
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
                    time_cfd.datetime = dt.astimezone(pytz.UTC)
                    time_cfd.timezone = timezone
                    log.debug(f'patch updated datetime+timezone on {time_cfd}')
                return True
            # this is the wonky bit, we have no time_cfd - we have to create ComplexDateTime based on only one of datetime/specificity
            #   the hope is that the next patch op will add/replace the other attribute
            if not dt:
                dt = datetime.datetime.utcnow()
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
            return True

        elif field == 'time' and isinstance(value, dict):
            time_cfd = ComplexDateTime.from_dict(value)
            with db.session.begin(subtransactions=True):
                db.session.add(time_cfd)
            old_cdt = ComplexDateTime.query.get(obj.time_guid)
            if old_cdt:
                with db.session.begin(subtransactions=True):
                    db.session.delete(old_cdt)
            obj.time = time_cfd
            obj.time_guid = time_cfd.guid
            return True

        else:
            log.error(
                f'patch_replace_helper given invalid args (field={field}, value={value})'
            )
            return False

    # for equality, must share same specificity too
    #  so cdt1 == cdt2 only when they are same utc datetime and same specificity
    def __eq__(self, other):
        if not isinstance(other, ComplexDateTime):
            return False
        return self.datetime == other.datetime and self.specificity == other.specificity

    def __ne__(self, other):
        return not self == other

    # this compares all attributes, not just datetime
    def is_identical(self, other):
        if not isinstance(other, ComplexDateTime):
            return False
        if self.specificity != other.specificity:
            return False
        # this is a bit of a reach.... since there are synonyms for "identical" timezones, we cannot just compare
        #   self.timezone == other.timezone; so, instead we compare their isoformat strings and hope for the best!
        return self.isoformat_in_timezone() == other.isoformat_in_timezone()

    # for these comparators, we return NotImplemented when specificities do not match, as we basically cant compare
    def __lt__(self, other):
        self._check_comparability(other)
        return self.datetime < other.datetime

    def __le__(self, other):
        self._check_comparability(other)
        return self.datetime <= other.datetime

    def __gt__(self, other):
        self._check_comparability(other)
        return self.datetime > other.datetime

    def __ge__(self, other):
        self._check_comparability(other)
        return self.datetime >= other.datetime

    def _check_comparability(self, other):
        if not isinstance(other, ComplexDateTime):
            raise NotImplementedError('comparing to incompatible type')
        if self.specificity != other.specificity:
            raise NotImplementedError('mismatched specificities; cannot compare')
