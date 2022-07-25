# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Ecological Data Management (EDM) manager.
No longer used in main Houston code but retained to allow data transfer from EDM
"""
import keyword
import logging

from flask import current_app, render_template, request, session  # NOQA
from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog  # NOQA
from app.extensions.restManager.RestManager import RestManager
from app.utils import HoustonException
from flask_restx_patched import is_extension_enabled

if not is_extension_enabled('edm'):
    raise RuntimeError('EDM is not enabled')


KEYWORD_SET = set(keyword.kwlist)

log = logging.getLogger(__name__)


class EDMManager(RestManager):
    """
        note the content of User in the 2nd item has stuff you can ignore. it also has the id as "uuid" (which is what it is internally, sigh).  also note it references Organizations !  we didnt touch on this on the call, but i think this should (must?) live with Users.  what we have in java is very lightweight anyway, so no loss to go away.   as you can see, user.organizations is an array of orgs, and (since it is many-to-many) you will see org.members is a list of Users.  easy peasy.  btw, by the time we got to Organizations, we did call the primary key id and make it a uuid.  "live and learn".  :confused:
    also!  the user.profileAsset is fabricated!  ben wanted something so i literally hardcoded a random choice (including empty) from a list of like 4 user faces. haha.  so you arent going crazy if you see this change per user.  and obviously in the future the contents of this will be more whatever we land on for final asset format.

        btw, as a bonus.  here is what an Organization is on wildbook[edm] ... they are hierarchical -- which i would argue we drop!!  it was fun for playing with, but i do not want to have to support that when security starts using these!!!  (no real world orgs use this currently anyway, not in any important way.)   other than that (and killing it off!) there are .members and .logoAsset.  boringly simple.
    https://nextgen.dev-wildbook.org/api/org.ecocean.Organization?id==%273b868b21-729f-46ca-933f-c4ecdf02e97d%27
    """

    NAME = 'EDM'
    ENDPOINT_PREFIX = 'api'

    # this is based on edm date of most recent commit (we must be at or greater than this)
    MIN_VERSION = '2022-02-02 12:34:56 -0700'

    # We use // as a shorthand for prefix
    # fmt: off
    ENDPOINTS = {
        'session': {
            'login': '//v0/login?content={"login":"%s","password":"%s"}',
        },
        'user': {
            'list': '//v0/org.ecocean.User/list',
            'data': '//v0/org.ecocean.User/%s',
            'data_complete': '//v0/org.ecocean.User/%s?detail-org.ecocean.User=max',
        },
        'encounter': {
            'list': '//v0/org.ecocean.Encounter/list',
            'data': '//v0/org.ecocean.Encounter/%s',
            'data_complete': '//v0/org.ecocean.Encounter/%s?detail-org.ecocean.Encounter=max',
        },
        'sighting': {
            'list': '//v0/org.ecocean.Occurrence/list',
            'data': '//v0/org.ecocean.Occurrence/%s',
            'data_complete': '//v0/org.ecocean.Occurrence/%s?detail-org.ecocean.Occurrence=max&detail-org.ecocean.Encounter=max',
        },
        'individual': {
            'list': '//v0/org.ecocean.MarkedIndividual/list',
            'data': '//v0/org.ecocean.MarkedIndividual/%s',
            'data_complete': '//v0/org.ecocean.MarkedIndividual/%s?detail-org.ecocean.MarkedIndividual=max',
            'merge': '//v0/merge',
        },
        'organization': {
            'list': '//v0/org.ecocean.Organization/list',
            'data': '//v0/org.ecocean.Organization/%s',
        },
        'collaboration': {
            'list': '//v0/org.ecocean.security.Collaboration/list',
        },
        'role': {
            'list': '//v0/org.ecocean.Role/list',
        },
        'passthrough': {
            'data': '',
        },
        'configuration': {
            'data': '//v0/configuration/%s',
            'init': '//v0/init?content=%s',
        },
        'configurationDefinition': {
            'data': '//v0/configurationDefinition/%s',
        },
        'version': {
            'dict': '/edm/json/git-info.json',
        }
    }
    # fmt: on

    def __init__(self, pre_initialize=False, *args, **kwargs):
        super(EDMManager, self).__init__(pre_initialize, *args, **kwargs)

    def initialize_edm_admin_user(self, email, password):
        import json

        edm_data = {
            'admin_user_initialized': {
                'email': email,
                'password': password,
                'username': email,
            }
        }
        target = 'default'  # TODO will we create admin on other targets?
        data = current_app.edm.get_dict(
            'configuration.init',
            json.dumps(edm_data),
            target=target,
        )
        if data.get('success', False):
            log.info(f'Success creating startup (edm) admin user via API: {email}.')
            return True
        else:
            log.warning(
                f'Failed creating startup (edm) admin user {email} via API. (response {data})'
            )
            return False

    # The edm API returns a success and a result, this processes it to raise an exception on any
    # error and provide validated parsed output for further processing
    def request_passthrough_parsed(
        self,
        tag,
        method,
        passthrough_kwargs,
        args=None,
        target='default',
        request_headers=None,
    ):

        # here we handle special headers needed specifically for EDM, which come via incoming request_headers
        if request_headers is not None:
            headers = passthrough_kwargs.get('headers', {})
            headers['x-allow-delete-cascade-individual'] = request_headers.get(
                'x-allow-delete-cascade-individual', 'false'
            )
            headers['x-allow-delete-cascade-sighting'] = request_headers.get(
                'x-allow-delete-cascade-sighting', 'false'
            )
            passthrough_kwargs['headers'] = headers
        response = self.request_passthrough(tag, method, passthrough_kwargs, args, target)
        response_data = None
        result_data = None
        try:
            response_data = response.json()
        except Exception:
            pass
        if response.ok and response_data is not None:
            result_data = response_data.get('result', None)

        if (
            not response.ok
            or not response_data.get('success', False)
            or response.status_code != 200
        ):
            status_code = response.status_code
            if status_code > 600:
                status_code = 400  # flask doesnt like us to use "invalid" codes. :(

            message = {'unknown error'}
            error = None

            if response_data is not None and 'message' in response_data:
                message = response_data['message']
            if response_data is not None and 'errorFields' in response_data:
                error = response_data['errorFields']

            raise HoustonException(
                log,
                f'{tag} {method} failed {message} {response.status_code}',
                AuditLog.AuditType.BackEndFault,
                status_code=status_code,
                message=message,
                error=error,
                edm_status_code=response.status_code,
                response_data=response_data,
            )

        return response, response_data, result_data

    # Provides the same validation and exception raising as above but just returns the result
    def request_passthrough_result(
        self, tag, method, passthrough_kwargs, args=None, request_headers=None
    ):
        response, response_data, result = self.request_passthrough_parsed(
            tag,
            method,
            passthrough_kwargs,
            args,
            request_headers=request_headers,
        )
        return result


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.edm = EDMManager()
