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
        current_app.edm.ensure_initialed()
        targets = list(current_app.edm.targets)
        return targets


@edm_configurationDefinition.route('/<string:target>/<path:path>')
# @edm_configurationDefinition.login_required(oauth_scopes=['configuration:read'])
class EDMConfigurationDefinition(Resource):
    """
    Configuration Definitions
    """

    def get(self, target, path):
        current_app.edm.ensure_initialed()
        targets = list(current_app.edm.targets)
        # Check target
        current_app.edm.ensure_initialed()
        targets = list(current_app.edm.targets)
        if target not in targets:
            raise BadRequest('The specified target %r is invalid.' % (target,))
        endpoint_url_ = current_app.edm.get_target_endpoint_url(target)
        endpoint = '%s/api/v0/configurationDefinition/%s' % (
            endpoint_url_,
            path,
        )
        request_func = current_app.edm.get_passthrough
        response = request_func(
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


def _request_passthrough(target, path, request_func, passthrough_kwargs):
    try:
        # Try to convert string integers to integers
        target = int(target)
    except ValueError:
        pass

    # Check target
    current_app.edm.ensure_initialed()
    targets = list(current_app.edm.targets)
    if target not in targets:
        raise BadRequest('The specified target %r is invalid.' % (target,))

    endpoint_url_ = current_app.edm.get_target_endpoint_url(target)
    endpoint = '%s/api/v0/configuration/%s' % (
        endpoint_url_,
        path,
    )

    headers = passthrough_kwargs.get('headers', {})
    allowed_header_key_list = [
        'Accept',
        'Content-Type',
        'User-Agent',
    ]
    is_json = False
    for header_key in allowed_header_key_list:
        header_value = request.headers.get(header_key, None)
        header_existing = headers.get(header_key, None)
        if header_value is not None and header_existing is None:
            headers[header_key] = header_value

        if header_key == 'Content-Type':
            if header_value is not None:
                if header_value.lower().startswith(
                    'application/javascript'
                ) or header_value.lower().startswith('application/json'):
                    is_json = True
    passthrough_kwargs['headers'] = headers

    if is_json:
        data_ = passthrough_kwargs.pop('data', None)
        if data_ is not None:
            passthrough_kwargs['json'] = data_

    response = request_func(
        None,
        endpoint=endpoint,
        target=target,
        decode_as_object=False,
        decode_as_dict=False,
        passthrough_kwargs=passthrough_kwargs,
    )
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

        request_func = current_app.edm.get_passthrough
        passthrough_kwargs = {'params': params}

        response = _request_passthrough(target, path, request_func, passthrough_kwargs)

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

        request_func = current_app.edm.post_passthrough

        passthrough_kwargs = {'data': data}

        files = request.files
        if len(files) > 0:
            passthrough_kwargs['files'] = files

        response = _request_passthrough(target, path, request_func, passthrough_kwargs)

        return response
