# -*- coding: utf-8 -*-
"""
Serialization schemas for Site Settings resources RESTful API
----------------------------------------------------
"""
from flask_marshmallow import base_fields

from app.extensions import ExtraValidationSchema
from flask_restx_patched import ModelSchema

from .models import SiteSetting


class BaseSiteSettingFileSchema(ModelSchema):
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


class DetailedSiteSettingFileSchema(BaseSiteSettingFileSchema):
    """
    Detailed SiteSetting schema exposes all useful fields.
    """

    class Meta(BaseSiteSettingFileSchema.Meta):
        fields = BaseSiteSettingFileSchema.Meta.fields + (
            SiteSetting.created.key,
            SiteSetting.updated.key,
            SiteSetting.string.key,
            SiteSetting.data.key,
        )
        dump_only = BaseSiteSettingFileSchema.Meta.dump_only + (
            SiteSetting.created.key,
            SiteSetting.updated.key,
        )


class RelationshipTypeSchema(ExtraValidationSchema):
    class RelationshipTypeRolesSchema(ExtraValidationSchema):
        guid = base_fields.UUID(required=True)
        label = base_fields.String(required=True)

    guid = base_fields.UUID(required=True)
    label = base_fields.String(required=True)
    roles = base_fields.Nested(RelationshipTypeRolesSchema, required=True, many=True)
