# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Configuration resources
--------------------------
"""

import logging

from flask import current_app, request
from flask_restplus_patched import Resource
from flask_restplus._http import HTTPStatus
from app.extensions.api import Namespace
from app.extensions.api import abort

from app.modules.users.models import User

from werkzeug.exceptions import BadRequest

import json


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
edm_configuration = Namespace(
    'configuration', description='(EDM) Configuration'
)  # pylint: disable=invalid-name
edm_configurationDefinition = Namespace(
    'configurationDefinition', description='(EDM) Configuration Definition'
)  # pylint: disable=invalid-name


@edm_configuration.route('/')
@edm_configuration.login_required(oauth_scopes=['configuration:read'])
class EDMConfigurationTargets(Resource):
    """
    Manipulations with Configuration.
    """

    def get(self):
        """
        List the possible EDM passthrough targets.
        """
        targets = current_app.edm.get_target_list()
        return targets


@edm_configurationDefinition.route('/<string:target>/<path:path>')
# @edm_configurationDefinition.login_required(oauth_scopes=['configuration:read'])
class EDMConfigurationDefinition(Resource):
    """
    Configuration Definitions
    """

    def get(self, target, path):

        # Check target
        targets = current_app.edm.get_target_list()

        if target not in targets:
            raise BadRequest('The specified target %r is invalid.' % (target,))
        endpoint_url_ = current_app.edm.get_target_endpoint_url(target)
        endpoint = '%s/api/v0/configurationDefinition/%s' % (
            endpoint_url_,
            path,
        )

        # @jon so why is configurationDefinition different in that it does not do the headers part that is
        # common to all other request_passthrough functionality
        response = current_app.edm.get_passthrough(
            None,
            endpoint=endpoint,
            target=target,
            decode_as_object=False,
            decode_as_dict=False,
        )
        data = response.json()
        if (
            response.ok
            and 'response' in data
            and 'isPrivate' in data['response']
            and data['response']['isPrivate']
            and 'value' in data['response']
        ):
            data['response'].pop('value')
            return data

        return response


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

        response = current_app.edm.request_passthrough(
            'configuration.data', 'get', {'params': params}, path, target
        )

        # private means cannot be read other than admin
        ####@edm_configuration.login_required(oauth_scopes=['configuration:write'])  TODO somehow need to *allow* private if has auth!!!
        data = response.json()
        if (
            response.ok
            and 'response' in data
            and 'private' in data['response']
            and data['response']['private']
        ):
            abort(code=HTTPStatus.FORBIDDEN, message='unavailable')

        if path == '__bundle_setup':
            data = response.json()
            data['response']['configuration'][
                'site.adminUserInitialized'
            ] = User.admin_user_initialized()
            return data

        return response

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
