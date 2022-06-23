# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Sage resources
--------------------------
"""

import logging

from flask import current_app

from app.extensions.api import Namespace
from flask_restx_patched import Resource

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

sage = Namespace('sage', description='Sage')


@sage.route('/jobs')
@sage.login_required(oauth_scopes=['sage:read'])
class SageJobs(Resource):
    r"""
    The jobs that Sage currently has
    """

    def get(self):
        return current_app.sage.request_passthrough_result('engine.list', 'get')[
            'json_result'
        ]
