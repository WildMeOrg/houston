# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for SiteSetting resources RESTful API
------------------------------------------------------------------
"""

from flask_restx_patched import Parameters

from . import schemas


class CreateSiteSettingFileParameters(Parameters, schemas.DetailedSiteSettingFileSchema):
    class Meta(schemas.DetailedSiteSettingFileSchema.Meta):
        fields = schemas.DetailedSiteSettingFileSchema.Meta.fields + (
            'transactionId',
            'transactionPath',
        )
