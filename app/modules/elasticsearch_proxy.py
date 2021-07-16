# -*- coding: utf-8 -*-
import logging

from flask import current_app, request
from flask_restx_patched import Resource

from app.extensions.api import api_v1, Namespace


log = logging.getLogger(__name__)
ns = Namespace('search', description='Search')


def init_app(app, **kwargs):
    api_v1.add_namespace(ns)


@ns.route('/<string:index>')
class SearchIndex(Resource):
    def post(self, index):
        body = request.get_data()
        resp = current_app.elasticsearch.search(index=index, body=body)
        return resp
