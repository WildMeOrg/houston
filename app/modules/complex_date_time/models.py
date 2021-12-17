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

    def get_datetime_timezone(self):
        return self.datetime.astimezone(self.get_timezone_object())

    def get_timezone_normalized(self):
        return normalized_timezone_string(self.get_datetime_timezone())

    def isoformat_utc(self):
        return self.datetime.isoformat()

    def isoformat_timezone(self):
        return self.get_datetime_timezone().isoformat()
