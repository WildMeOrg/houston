# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API FileUploads resources
--------------------------
Currently our standard CRUD is _disabled_ for FileUpload objects.  They should only be accessed via other API calls
which will set FileUpload values as properties on other objects.
"""

import logging
import pathlib

from flask import send_file, request, current_app
from flask_login import current_user  # NOQA
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from app.extensions.api import Namespace, abort

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


@api.route('/image_validate')
class FlatfileImageNameValidate(Resource):
    # values passed in from flatfile are val/index pairs:
    # [
    #   ["1.jpg", 1],
    #   ["86.jpg,zebra.jpg", 2],
    #   ["55.jpg, giraffe.jpg", ", 15],
    # ]
    def post(self):
        from app.utils import get_stored_filename
        from os.path import is_file

        if not current_user or current_user.is_anonymous:
            abort(code=401)

        # TODO: make sure user is logged in?
        if not isinstance(request.json, list):
            abort(
                message='Must be passed a list of flatfile-formatted image names-index pairs',
                code=500,
            )

        fnames_strs = [val_id_pair[0] for val_id_pair in request.json]
        fnames_ids = [val_id_pair[1] for val_id_pair in request.json]

        transaction_id = current_user.get_bulk_tus_transaction_id
        assert (
            transaction_id
        ), f'could not find an active bulk transaction_id for {current_user}'

        fileupload_base_path = pathlib.Path(
            current_app.config.get('FILEUPLOAD_BASE_PATH')
        )
        user_dir = f'{fileupload_base_path}/trans-{transaction_id}'

        rtn_json = []
        for fnames_str, index in zip(fnames_strs, fnames_ids):

            # parse comma-separated, possibly whitespace-separated filenames
            fname_list = fnames_str.split(',')
            fname_list = [fname.strip() for fname in fname_list]

            hashed_fnames = [get_stored_filename(fname) for fname in fname_list]
            missing_images = [
                fname
                for fname, hashed_fname in zip(fname_list, hashed_fnames)
                if not is_file(f'{user_dir}/{hashed_fname}')
            ]

            if len(missing_images) == 0:
                row_json = {
                    'message': 'images uploaded successfully.',
                    'level': 'info',
                }
            elif len(missing_images) == 1:
                row_json = {
                    'message': f'missing image: {missing_images[0]}. please return to image upload stage and upload this image.',
                    'level': 'error',
                }
            else:
                row_json = {
                    'message': f'missing images: {missing_images}. please return to image upload stage and upload these images.',
                    'level': 'error',
                }

            rtn_json.append([row_json, index])

        return rtn_json
