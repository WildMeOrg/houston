# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for FileUploads resources RESTful API
-----------------------------------------------------------
"""

# from flask_marshmallow import base_fields
from flask_restx_patched import Parameters

from . import schemas

# from .models import FileUpload


class CreateFileUploadParameters(Parameters, schemas.DetailedFileUploadSchema):
    class Meta(schemas.DetailedFileUploadSchema.Meta):
        pass
