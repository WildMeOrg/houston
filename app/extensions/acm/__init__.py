# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Asset Curation Model (ACM) manager.

"""

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
from app.extensions.restManager.RestManager import RestManager
from app.extensions.task_manager import TaskManager
import logging

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
        }
    }
    # fmt: on

    def __init__(self, pre_initialize=False, *args, **kwargs):
        super(ACMManager, self).__init__(pre_initialize, *args, **kwargs)

    def _ensure_initialized(self):
        super(ACMManager, self)._ensure_initialized()
        # Check on what the jobs are doing every half hour
        TaskManager.register_callback(30, self.periodic)

    def periodic(self):
        # Presume this is where we would check jobs
        pass


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.acm = ACMManager()
