# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Configuration resources
--------------------------
"""

import logging

from flask import current_app, request
from flask_restx_patched import Resource
from app.extensions.api import Namespace

from app.modules.users.models import User

import json


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
edm_configuration = Namespace(
    'configuration', description='(EDM) Configuration'
)  # pylint: disable=invalid-name
edm_configurationDefinition = Namespace(
    'configurationDefinition', description='(EDM) Configuration Definition'
)  # pylint: disable=invalid-name


@edm_configurationDefinition.route('/<string:target>/<path:path>')
# @edm_configurationDefinition.login_required(oauth_scopes=['configuration:read'])
class EDMConfigurationDefinition(Resource):
    """
    Configuration Definitions
    """

    def get(self, target, path):
        data = current_app.edm.get_dict(
            'configurationDefinition.data',
            path,
            target=target,
            ensure_initialized=False,
        )
        # TODO also traverse private here FIXME
        return data


@edm_configuration.route('/<string:target>', defaults={'path': ''}, doc=False)
@edm_configuration.route('/<string:target>/<path:path>')
# @edm_configuration.login_required(oauth_scopes=['configuration:read'])
class EDMConfiguration(Resource):
    r"""
    A pass-through allows a GET or POST request to be referred to a registered back-end EDM

    CommandLine:
        EMAIL='test@localhost'
        PASSWORD='test'
        TIMESTAMP=$(date '+%Y%m%d-%H%M%S%Z')
        curl \
            -X POST \
            -c cookie.jar \
            -H 'Content-Type: multipart/form-data' \
            -H 'Accept: application/json' \
            -F email=${EMAIL} \
            -F password=${PASSWORD} \
            https://wildme.ngrok.io/api/v1/auth/sessions | jq
        curl \
            -X GET \
            -b cookie.jar \
            https://wildme.ngrok.io/api/v1/users/me | jq
        curl \
            -X POST \
            -b cookie.jar \
            -H 'Content-type: application/javascript' \
            -d "{\"site.name\": \"value-updated-${TIMESTAMP}\"}" \
            https://wildme.ngrok.io/api/v1/configuration/default/api/v0/configuration | jq
        curl \
            -X GET \
            -b cookie.jar \
            https://wildme.ngrok.io/api/v1/configuration/edm/default/api/v0/configuration/site.name | jq ".response.value"
    """

    def get(self, target, path):
        params = {}
        params.update(request.args)
        params.update(request.form)

        data = current_app.edm.get_dict(
            'configuration.data',
            path,
            target=target,
            ensure_initialized=False,
        )

        # TODO make private private - traverse bundles too
        # private means cannot be read other than admin
        # abort(code=HTTPStatus.FORBIDDEN, message='unavailable')

        if path == '__bundle_setup':
            data['response']['configuration'][
                'site.adminUserInitialized'
            ] = User.admin_user_initialized()
        return data

    @edm_configuration.login_required(oauth_scopes=['configuration:write'])
    def post(self, target, path):
        data = {}
        data.update(request.args)
        data.update(request.form)
        try:
            data_ = json.loads(request.data)
            data.update(data_)
        except Exception:
            pass

        passthrough_kwargs = {'data': data}

        files = request.files
        if len(files) > 0:
            passthrough_kwargs['files'] = files

        response = current_app.edm.request_passthrough(
            'configuration.data', 'post', passthrough_kwargs, path, target
        )

        return response
