# -*- coding: utf-8 -*-
"""
Serialization schemas for FileUploads resources RESTful API
----------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restx_patched import ModelSchema

from .models import FileUpload


class BaseFileUploadSchema(ModelSchema):
    """
    Base FileUpload schema exposes only the most general fields.
    """

    class Meta:
        # pylint: disable=missing-docstring
        model = FileUpload
        fields = (FileUpload.guid.key,)
        dump_only = (FileUpload.guid.key,)


class DetailedFileUploadSchema(BaseFileUploadSchema):
    """
    Detailed FileUpload schema exposes all useful fields.
    """

    class Meta(BaseFileUploadSchema.Meta):
        fields = BaseFileUploadSchema.Meta.fields + (
            FileUpload.created.key,
            FileUpload.updated.key,
            FileUpload.mime_type.key,
            'src',
        )
        dump_only = BaseFileUploadSchema.Meta.dump_only + (
            FileUpload.created.key,
            FileUpload.updated.key,
        )
