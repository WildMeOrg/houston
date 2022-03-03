# -*- coding: utf-8 -*-
"""
Elasticsearch module
====================
"""

from app.extensions.api import api_v1

from app.modules import is_module_enabled

if not is_module_enabled('elasticsearch'):
    raise RuntimeError('Elasticsearch (module) is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init elasticsearch module.
    """
    # api_v1.add_oauth_scope('search:read', 'Provide access to search')

    # Touch underlying modules
    from . import resources  # NOQA

    api_v1.add_namespace(resources.api)
