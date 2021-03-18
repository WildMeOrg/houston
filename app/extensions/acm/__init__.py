# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Asset Curation Model (ACM) manager.

"""
import logging

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
from app.extensions.restManager.RestManager import RestManager

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
        'session': {
            'login': '//v0/login?content={"login":"%s","password":"%s"}',
        },
    }
    # fmt: on

    def __init__(self, app, pre_initialize=False, *args, **kwargs):
        super(ACMManager, self).__init__(app, pre_initialize, *args, **kwargs)


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    ACMManager(app)
