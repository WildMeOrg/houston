# -*- coding: utf-8 -*-
"""
Keywords module
============
"""

from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('keywords'):
    raise RuntimeError('Keywords is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Keywords module.
    """
    api_v1.add_oauth_scope('keywords:read', 'Provide access to Keywords details')
    api_v1.add_oauth_scope('keywords:write', 'Provide write access to Keywords details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
