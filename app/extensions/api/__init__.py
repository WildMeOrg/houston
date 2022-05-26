# -*- coding: utf-8 -*-
"""
API extension
=============
"""

import logging
from copy import deepcopy

from flask import Blueprint, current_app  # NOQA

from app.version import version

from .api import Api  # NOQA
from .http_exceptions import abort  # NOQA
from .namespace import Namespace  # NOQA

log = logging.getLogger(__name__)


api_v1_blueprint = Blueprint('api', __name__, url_prefix='/api/v1')
api_v1 = Api(  # pylint: disable=invalid-name
    api_v1_blueprint,
    version='Version: {}'.format(version),
    contact='info@wildme.org',
    # license='Apache License 2.0',
    # license_url='https://www.apache.org/licenses/LICENSE-2.0',
)


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    # Prevent config variable modification with runtime changes
    api_v1.authorizations = deepcopy(app.config['AUTHORIZATIONS'])
    api_v1.title = f"Wild Me {app.config['PROJECT_NAME']}"
    app.register_blueprint(api_v1_blueprint)
