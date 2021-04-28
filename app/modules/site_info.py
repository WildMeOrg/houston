# -*- coding: utf-8 -*-
from flask import current_app

import app.version
from app.extensions.api import api_v1, Namespace
from flask_restx_patched import Resource


site_info_api = Namespace('site-info', description='Site Info')


def init_app(app, **kwargs):
    api_v1.add_namespace(site_info_api)


@site_info_api.route('/')
class SiteInfo(Resource):
    def get(self):
        acm_version = current_app.acm.get_dict('version.dict', None)
        if isinstance(acm_version, dict):
            acm_version = acm_version['response']
        else:
            # acm returns a non 200 response
            acm_version = repr(acm_version)
        edm_version = current_app.edm.get_dict('version.dict', None)
        if not isinstance(edm_version, dict):
            # edm returns a non 200 response
            edm_version = repr(edm_version)
        return {
            'houston': {
                'version': app.version.version,
                'git_version': app.version.git_revision,
            },
            'acm': acm_version,
            'edm': edm_version,
        }
