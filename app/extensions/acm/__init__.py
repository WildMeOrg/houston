# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Asset Curation Model (ACM) manager.

"""

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
from app.extensions.restManager.RestManager import RestManager
from app.utils import HoustonException

import logging
import keyword

from flask_restx_patched import is_extension_enabled

if not is_extension_enabled('acm'):
    raise RuntimeError('ACM is not enabled')


KEYWORD_SET = set(keyword.kwlist)

log = logging.getLogger(__name__)


def to_acm_uuid(uuid):
    return {'__UUID__': str(uuid)}


def from_acm_uuid(uuid_str):
    import uuid

    assert '__UUID__' in uuid_str.keys()
    return uuid.UUID(uuid_str['__UUID__'])


class ACMManager(RestManager):
    # pylint: disable=abstract-method
    """"""
    NAME = 'ACM'
    ENDPOINT_PREFIX = 'api'
    # We use // as a shorthand for prefix
    # fmt: off
    ENDPOINTS = {
        # No user.session, wbia doesn't support logins
        'annotations': {
            'list': '//annot/json/',
            'data': '//annot/name/uuid/json/?annot_uuid_list=[{"__UUID__": "%s"}]',
        },
        'assets': {
            'list': '//image/json/',
        },
        'version': {
            'dict': '//version/',
        },
        'passthrough': {
            'data': '',
        },
        'job': {
            'detect_request': '//engine/detect/%s',
            'identification_request': '//engine/query/graph/',
            'response': '//engine/job/result/?jobid=%s'
        }
    }
    # fmt: on

    def __init__(self, pre_initialize=False, *args, **kwargs):
        super(ACMManager, self).__init__(pre_initialize, *args, **kwargs)

    # The acm API returns a status and a response, this processes it to raise an exception on any
    # error and provide validated parsed output for further processing
    def request_passthrough_parsed(
        self, tag, method, passthrough_kwargs, args=None, target='default'
    ):
        import app.extensions.logging as AuditLog  # NOQA

        response = self.request_passthrough(tag, method, passthrough_kwargs, args, target)

        # Sage sent invalid response
        try:
            response_json = response.json()
        except Exception:
            message = (f'{tag} {method} failed to parse json response from Sage',)
            raise HoustonException(
                log,
                f'{message} Sage Status:{response.status_code} Sage Reason: {response.reason}',
                AuditLog.AuditType.BackEndFault,
                message=message,
            )

        # Sage sent invalid response
        status_data = response_json.get('status', None)
        if not status_data:
            message = (f'{tag} {method} failed to parse json status data from Sage',)
            raise HoustonException(
                log,
                f'{message} Sage Status:{response.status_code} Sage Reason: {response.reason}',
                AuditLog.AuditType.BackEndFault,
                message=message,
            )

        # status is correctly formatted, see if it failed
        response_data = response_json.get('response', None)
        if (
            not response.ok
            or not status_data.get('success', False)
            or response.status_code != 200
            or response_data is None
        ):
            log_message = status_data.get('message', response.reason)
            #  Don't report internal Sage Errors to the frontend
            message = 'failed to start Sage request'

            status_code = response.status_code
            if status_code > 600:
                status_code = 400  # flask doesnt like us to use "invalid" codes. :(
            raise HoustonException(
                log,
                f'{tag} {method} failed {log_message} {response.status_code}',
                AuditLog.AuditType.BackEndFault,
                status_code=status_code,
                message=message,
                acm_status_code=response.status_code,
            )

        return response, response_json, response_data

    # Provides the same validation and exception raising as above but just returns the result
    def request_passthrough_result(self, tag, method, passthrough_kwargs, args=None):
        response, response_data, result = self.request_passthrough_parsed(
            tag, method, passthrough_kwargs, args
        )
        return result


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.acm = ACMManager()
