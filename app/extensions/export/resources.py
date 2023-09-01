# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
RESTful API User resources
--------------------------
"""

import logging
from http import HTTPStatus

from app.extensions.api import Namespace, abort
from flask_restx_patched import Resource

log = logging.getLogger(__name__)


api = Namespace('export', description='Export xls')  # pylint: disable=invalid-name


@api.route('/<string:filename>')
# @api.login_required(oauth_scopes=['search:read'])
class ExportDownload(Resource):
    def get(self, filename):
        abort(
            # HTTPStatus.FORBIDDEN,
            HTTPStatus.CONFLICT,
            f'nope {filename}',
        )
        return None
