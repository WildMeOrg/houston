# -*- coding: utf-8 -*-
"""
AccountRequest module
============
"""

from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('account_requests'):
    raise RuntimeError('AccountRequests is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init AccountRequest module.
    """
    api_v1.add_oauth_scope(
        'account_requests:read', 'Provide access to AccountRequest details'
    )
    api_v1.add_oauth_scope(
        'account_requests:write', 'Provide write access to AccountRequest details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    # register_elasticsearch_model(models.AccountRequests)
