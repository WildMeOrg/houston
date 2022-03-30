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


@api.route('/')
@api.login_required(oauth_scopes=['search:read'])
class ElasticsearchListIndices(Resource):
    def get(self):
        from app.extensions import elasticsearch as es

        indices = es.es_all_indices()
        return indices


@api.route('/<string:index>/mappings')
@api.login_required(oauth_scopes=['search:read'])
class ElasticsearchMappings(Resource):
    def get(self, index):
        from app.extensions import elasticsearch as es

        mappings = es.es_index_mappings(index)
        return mappings


@api.route('/status')
@api.login_required(oauth_scopes=['search:read'])
class ElasticsearchStatus(Resource):
    """Check the search status of the elasticsearch backend service"""

    def get(self):
        if is_extension_enabled('elasticsearch'):
            from app.extensions import elasticsearch as es

            status = es.es_status()
        else:
            status = {}

        return status


@api.route('/sync')
@api.login_required(oauth_scopes=['search:read'])
class ElasticsearchSync(Resource):
    """Force a re-indexing with Elasticsearch"""

    def get(self):
        if is_extension_enabled('elasticsearch'):
            from app.extensions import elasticsearch as es

            with es.session.begin(blocking=True, forced=False, verify=True):
                es.es_index_all()

            status = es.es_status()
        else:
            status = {}

        return status


@api.route('/proxy/<string:index>')
# @api.login_required(oauth_scopes=['search:read'])
class ElasticsearchProxy(Resource):
    def post(self, index):
        body = request.get_data()
        resp = current_app.elasticsearch.search(index=index, body=body)
        return resp
