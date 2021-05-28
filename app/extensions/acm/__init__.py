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

KEYWORD_SET = set(keyword.kwlist)

log = logging.getLogger(__name__)


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
    }
    # fmt: on

    def __init__(self, pre_initialize=False, *args, **kwargs):
        super(ACMManager, self).__init__(pre_initialize, *args, **kwargs)

    # TODO if this is exactly what acm returns then move both these functions into the RestManager
    # The edm API returns a success and a result, this processes it to raise an exception on any
    # error and provide validated parsed output for further processing
    def request_passthrough_parsed(
        self, tag, method, passthrough_kwargs, args=None, target='default'
    ):
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
            or result_data is None
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
                status_code=status_code,
                message=message,
                log_message=f'{tag} {method} failed {message}',
                error=error,
                edm_status_code=response.status_code,
            )

        return response, response_data, result_data

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
