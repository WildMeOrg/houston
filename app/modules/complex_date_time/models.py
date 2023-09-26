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

    @classmethod
    def check_config_data_validity(cls, data):
        error = None
        if not data or not isinstance(data, dict):
            error = 'No data passed in'
        elif 'time' not in data:
            error = 'time field missing'
        elif not isinstance(data['time'], str):
            error = 'time field must be a string'
        elif 'timeSpecificity' not in data:
            error = 'timeSpecificity field missing'
        elif not isinstance(data['timeSpecificity'], str):
            error = 'timeSpecificity field must be a string'

        if not error:
            date_time_str = data['time']
            try:
                # will throw ValueError if invalid
                date_time = datetime.datetime.fromisoformat(date_time_str)
                if not date_time.tzinfo:
                    error = f'timezone cannot be derived from time: {date_time_str}'
            except ValueError:
                error = f'time field is not a valid datetime: {date_time_str}'
            spec_string = data['timeSpecificity']
            if not Specificities.has_value(spec_string):
                error = f'timeSpecificity {spec_string} not supported'

        return error is None, error

    @classmethod
    def from_data(cls, data):
        is_valid, error = cls.check_config_data_validity(data)
        if not is_valid:
            AuditLog.frontend_fault(log, error)
            raise ValueError(error)

        date_time = datetime.datetime.fromisoformat(data['time'])
        timezone = cls._normalized_timezone_string(date_time)
        specificity = Specificities[data['timeSpecificity']]
        return ComplexDateTime(date_time, timezone, specificity)

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
        return self._normalized_timezone_string(self.get_datetime_in_timezone())

    # in a nutshell dt.tzname() *sucks*.  i am not sure what it is showing, but its bunk.
    #   this is an attempt to get a string *that can be read back in above*
    @classmethod
    def _normalized_timezone_string(cls, dt):
        if not dt or not isinstance(dt, datetime.datetime):
            raise ValueError('must pass datetime object')
        return dt.strftime('UTC%z')

    def isoformat_utc(self):
        return self.datetime.isoformat()

    def isoformat_in_timezone(self):
        return self.get_datetime_in_timezone().isoformat()

    @property
    def sort_value(self):
        from datetime import datetime

        ub = self.upper_bound
        lb = self.lower_bound
        diff = ub - lb
        return datetime.timestamp(lb + diff / 2)

    @property
    def lower_bound(self):
        from datetime import datetime

        if self.specificity == Specificities.time:
            return self.get_datetime_in_timezone()
        if self.specificity == Specificities.day:
            return datetime(
                self.datetime.year, self.datetime.month, self.datetime.day, 0, 0, 0
            ).astimezone(self.get_timezone_object())
        if self.specificity == Specificities.month:
            return datetime(
                self.datetime.year, self.datetime.month, 1, 0, 0, 0
            ).astimezone(self.get_timezone_object())
        return datetime(self.datetime.year, 1, 1, 0, 0, 0).astimezone(
            self.get_timezone_object()
        )

    @property
    def upper_bound(self):
        import calendar
        from datetime import datetime

        if self.specificity == Specificities.time:
            return self.get_datetime_in_timezone()
        if self.specificity == Specificities.day:
            return datetime(
                self.datetime.year, self.datetime.month, self.datetime.day, 23, 59, 59
            ).astimezone(self.get_timezone_object())
        if self.specificity == Specificities.month:
            cal = calendar.monthrange(self.datetime.year, self.datetime.month)
            return datetime(
                self.datetime.year, self.datetime.month, cal[1], 23, 59, 59
            ).astimezone(self.get_timezone_object())
        return datetime(self.datetime.year, 12, 31, 23, 59, 59).astimezone(
            self.get_timezone_object()
        )

    # used from parameters.py for object which have time/timeSpecifity patches (currently encounter and sighting)
    @classmethod
    def patch_replace_helper(cls, obj, field, value):
        import pytz

        from app.modules.complex_date_time.models import ComplexDateTime, Specificities

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
                timezone = cls._normalized_timezone_string(dt)
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
