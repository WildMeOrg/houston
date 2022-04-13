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


@api.route('/validate')
class FlatfileImageNameValidate(Resource):
    # values passed in from flatfile are val/index pairs:
    # [
    #   ["1.jpg", 1],
    #   ["86.jpg,zebra.jpg", 2],
    #   ["55.jpg, giraffe.jpg", ", 15],
    # ]
    def post(self):
        from app.modules.names.models import Name, DEFAULT_NAME_CONTEXT

        from flask_login import current_user
        from collections import defaultdict

        if not current_user or current_user.is_anonymous:
            abort(code=401)
        if not isinstance(request.json, list):
            abort(
                message='Must be passed a list of flatfile-formatted image names-index pairs',
                code=500,
            )

        fnames_index_dict = {
            val_id_pair[0]: val_id_pair[1] for val_id_pair in request.json
        }
        fnames_lists = [_comma_separated_fnames_to_list(fname) for fname in fnames_index_dict.keys()]
        fnames_list = [fname for fname in fname_list for fname_list in fname_lists]
        # want to preserve order here
        query_name_vals = [val_id_pair[0] for val_id_pair in request.json]


        db_names = Name.query.filter(
            Name.value.in_(query_name_vals), Name.context == DEFAULT_NAME_CONTEXT
        )
        # maps a name value to list of individuals with that name value
        db_name_lookup = defaultdict(list)
        for name in db_names:
            db_name_lookup[name.value].append(str(name.individual_guid))

        rtn_json = []
        for name_val in query_name_vals:
            if name_val in db_name_lookup and len(db_name_lookup[name_val]) == 1:
                name_info = {
                    'message': f'Corresponds to existing individual {db_name_lookup[name_val][0]}.',
                    'level': 'info',
                }
            elif name_val in db_name_lookup and len(db_name_lookup[name_val]) > 1:
                name_info = {
                    'message': f'ERROR: cannot resolve this name to a unique individual. Individuals sharing this name are {db_name_lookup[name_val]}.',
                    'level': 'error',
                }
            else:
                name_info = {
                    'message': 'This is a new name and submission will create a new individual',
                    'level': 'warning',
                }

            name_json = {'value': name_val, 'info': [name_info]}
            rtn_json.append([name_json, query_index_dict[name_val]])

        return rtn_json

    def _comma_separated_fnames_to_list(fnames_str):
        fname_list = fnames_str.split(",")
        # remove whitespace
        fname_list = [fname.strip() for fname in fnames]
        return fname_list
