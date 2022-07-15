# -*- coding: utf-8 -*-
"""
Serialization schemas for ComplexDateTimes resources RESTful API
----------------------------------------------------
"""

from flask_marshmallow import base_fields

from flask_restx_patched import ModelSchema

from .models import ComplexDateTime


class BaseComplexDateTimeSchema(ModelSchema):
    """
    Base ComplexDateTime schema exposes only the most general fields.
    """

    timezoneNormalized = base_fields.Function(lambda cdt: cdt.get_timezone_normalized())
    timeInTimezone = base_fields.Function(lambda cdt: cdt.isoformat_in_timezone())

    class Meta:
        # pylint: disable=missing-docstring
        model = ComplexDateTime
        fields = (
            ComplexDateTime.guid.key,
            ComplexDateTime.datetime.key,
            ComplexDateTime.timezone.key,
            ComplexDateTime.specificity.key,
        )
        dump_only = (ComplexDateTime.guid.key,)


class DetailedComplexDateTimeSchema(BaseComplexDateTimeSchema):
    """
    Detailed ComplexDateTime schema exposes all useful fields.
    """

    class Meta(BaseComplexDateTimeSchema.Meta):
        fields = BaseComplexDateTimeSchema.Meta.fields + (
            'timezoneNormalized',
            'timeInTimezone',
        )
        dump_only = BaseComplexDateTimeSchema.Meta.dump_only
