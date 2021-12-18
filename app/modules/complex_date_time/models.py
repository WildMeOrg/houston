# -*- coding: utf-8 -*-
"""
ComplexDateTime database models
A structure for holding a DateTime object with additional complexity
involving time zone and specificity
--------------------
"""
import uuid
import enum
from app.extensions import db
import logging

# import app.extensions.logging as AuditLog
from datetime import datetime
from dateutil import tz
from app.utils import normalized_timezone_string
import pytz

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Specificities(str, enum.Enum):
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
        if not dt or not isinstance(dt, datetime):
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

    datetime = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=False)

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
        dt = datetime(*parts, tzinfo=tz.gettz(timezone))
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
