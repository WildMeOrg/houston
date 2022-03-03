# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
RESTful API User resources
--------------------------
"""

import logging
from flask import current_app, request
from flask_restx_patched import Resource
from app.extensions.api import Namespace

from app.extensions import is_extension_enabled


log = logging.getLogger(__name__)
api = Namespace('search', description='Searching via Elasticsearch')


@api.route('/proxy/<string:index>')
# @api.login_required(oauth_scopes=['search:read'])
class ElasticsearchProxy(Resource):
    def post(self, index):
        body = request.get_data()
        resp = current_app.elasticsearch.search(index=index, body=body)
        return resp


@api.route('/status')
# @api.login_required(oauth_scopes=['search:read'])
class ElasticsearchStatus(Resource):
    """Check the search status of the elasticsearch backend service"""

    def get(self):
        if is_extension_enabled('elasticsearch'):
            from app.extensions import elasticsearch as es

            status = es.es_status()
        else:
            status = {}

        return status
