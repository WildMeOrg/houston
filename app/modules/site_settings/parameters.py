# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for SiteSetting resources RESTful API
------------------------------------------------------------------
"""

from flask_restx_patched import Parameters
from app.extensions.api.parameters import PaginationParameters
from flask_marshmallow import base_fields

from . import schemas


class ListSiteSettingsFile(PaginationParameters):
    sort = base_fields.String(
        description='the field to sort the results by, default is "key"',
        missing='key',
    )


class CreateSiteSettingFileParameters(Parameters, schemas.DetailedSiteSettingFileSchema):
    class Meta(schemas.DetailedSiteSettingFileSchema.Meta):
        fields = schemas.DetailedSiteSettingFileSchema.Meta.fields + (
            'transactionId',
            'transactionPath',
        )
