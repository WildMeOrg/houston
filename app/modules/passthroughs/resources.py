# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Passthroughs resources
--------------------------
"""

import json
import logging

from flask import current_app, request

from app.extensions.api import Namespace, abort
from flask_restx_patched import Resource

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
edm_pass = Namespace(
    'passthroughs/edm', description='EDM Passthroughs'
)  # pylint: disable=invalid-name
sage_pass = Namespace(
    'passthroughs/sage', description='Sage Passthroughs'
)  # pylint: disable=invalid-name


# Disabled, should probably be removed entirely
@edm_pass.route('/')
@edm_pass.login_required(oauth_scopes=['passthroughs:read'])
class EDMPassthroughTargets(Resource):
    """
    Manipulations with Passthroughs.
    """

    def get(self):
        """
        List the possible EDM passthrough targets.
        """
        targets = current_app.edm.get_target_list()
        return targets


# Disabled, should probably be removed entirely
@edm_pass.route('/<string:target>/', defaults={'path': None}, doc=False)
@edm_pass.route('/<string:target>/<path:path>')
@edm_pass.login_required(oauth_scopes=['passthroughs:read'])
class EDMPassthroughs(Resource):
    r"""
    A pass-through allows a GET or POST request to be referred to a registered back-end EDM

    CommandLine:
        EMAIL='test@localhost'
        PASSWORD='test'
        TIMESTAMP=$(date '+%Y%m%d-%H%M%S%Z')
        curl \
            -X POST \
            -c cookie.jar \
            -F email=${EMAIL} \
            -F password=${PASSWORD} \
            https://houston.dyn.wildme.io/api/v1/auth/sessions | jq
        curl \
            -X GET \
            -b cookie.jar \
            https://houston.dyn.wildme.io/api/v1/users/me | jq
        curl \
            -X POST \
            -b cookie.jar \
            -d "{\"site.name\": \"value-updated-${TIMESTAMP}\"}" \
            https://houston.dyn.wildme.io/api/v1/passthroughs/edm/default/api/v0/configuration | jq
        curl \
            -X GET \
            -b cookie.jar \
            https://houston.dyn.wildme.io/api/v1/passthroughs/edm/default/api/v0/configuration/site.name | jq ".response.value"
    """

    def get(self, target, path):
        """
        List the possible EDM passthrough targets.
        """
        params = {}
        params.update(request.args)
        params.update(request.form)

        response = current_app.edm.request_passthrough(
            'passthrough.data', 'get', {'params': params}, path, target
        )

        return response

    def post(self, target, path):
        """
        List the possible EDM passthrough targets.
        """
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
            'passthrough.data', 'post', passthrough_kwargs, path, target
        )

        return response


@sage_pass.route('/')
@sage_pass.login_required(oauth_scopes=['passthroughs:read'])
class SagePassthroughTargets(Resource):
    """
    List of Sage Passthrough targets supported.
    """

    def get(self):
        """
        List the possible Sage passthrough targets.
        """
        return ['jobs']


@sage_pass.route('/<string:target>/', doc=False)
@sage_pass.login_required(oauth_scopes=['passthroughs:read'])
class SagePassthroughs(Resource):
    r"""
    A pass-through allows certain "targets" as defined within Houston, to map to controlled requests to the
    appropriate Sage instance for this Platform
    """

    def get(self, target):
        """
        List the possible Sage passthrough targets.
        """

        response = {}
        if target == 'jobs':
            response = current_app.sage.request_passthrough_result('engine.list', 'get')[
                'json_result'
            ]
        else:
            abort(400, f'target {target} not supported')

        return response
