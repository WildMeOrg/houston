# -*- coding: utf-8 -*-
"""
Progress module
============
"""

from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('progress'):
    raise RuntimeError('Progress is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Progress module.
    """
    api_v1.add_oauth_scope('progress:read', 'Provide access to Progress details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
