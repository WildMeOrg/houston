# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API FileUploads resources
--------------------------
Currently our standard CRUD is _disabled_ for FileUpload objects.  They should only be accessed via other API calls
which will set FileUpload values as properties on other objects.
"""

import logging

from flask import send_file
from flask_login import current_user  # NOQA
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions.api import Namespace


from .models import FileUpload


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('fileuploads', description='FileUploads')  # pylint: disable=invalid-name


# NOTE format not yet implemented; just mimicking asset endpoints
#   permissions here are basically non-existent as viewing these objects is currently considered "public"; may change later!
@api.route('/src/<uuid:fileupload_guid>', defaults={'format': 'master'}, doc=False)
@api.route('/src/<string:format>/<uuid:fileupload_guid>')
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='FileUpload not found.',
)
@api.resolve_object_by_model(FileUpload, 'fileupload')
class FileUploadSrcUByID(Resource):
    def get(self, fileupload, format):
        return send_file(fileupload.get_absolute_path(), fileupload.mime_type)
