# -*- coding: utf-8 -*-
"""
Serialization schemas for Site Settings resources RESTful API
----------------------------------------------------
"""

from flask_restx_patched import ModelSchema

from .models import SiteSetting


class BaseSiteSettingSchema(ModelSchema):
    """
    Base SiteSetting schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = SiteSetting
        fields = (
            SiteSetting.key.key,
            SiteSetting.file_upload_guid.key,
            SiteSetting.public.key,
        )
        dump_only = ()


class DetailedSiteSettingSchema(BaseSiteSettingSchema):
    """
    Detailed SiteSetting schema exposes all useful fields.
    """

    class Meta(BaseSiteSettingSchema.Meta):
        fields = BaseSiteSettingSchema.Meta.fields + (
            SiteSetting.created.key,
            SiteSetting.updated.key,
            SiteSetting.string.key,
            SiteSetting.data.key,
        )
        dump_only = BaseSiteSettingSchema.Meta.dump_only + (
            SiteSetting.created.key,
            SiteSetting.updated.key,
        )
