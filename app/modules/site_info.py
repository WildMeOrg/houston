# -*- coding: utf-8 -*-
import app.version
from app.extensions.api import api_v1, Namespace
from flask_restx_patched import Resource


site_info_api = Namespace('site-info', description='Site Info')


def init_app(app, **kwargs):
    api_v1.add_namespace(site_info_api)


@site_info_api.route('/')
class SiteInfo(Resource):
    def get(self):
        return {
            'houston': {
                'version': app.version.version,
                'git_version': app.version.git_revision,
            },
        }
