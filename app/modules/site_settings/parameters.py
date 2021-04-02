# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for SiteSetting resources RESTful API
------------------------------------------------------------------
"""

from flask_restx_patched import Parameters

from . import schemas


class CreateSiteSettingParameters(Parameters, schemas.DetailedSiteSettingSchema):
    class Meta(schemas.DetailedSiteSettingSchema.Meta):
        fields = schemas.DetailedSiteSettingSchema.Meta.fields + (
            'transactionId',
            'transactionPath',
        )
