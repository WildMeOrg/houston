# -*- coding: utf-8 -*-
"""
Assets module
============
"""

from app.extensions import register_elasticsearch_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('assets'):
    raise RuntimeError('Assets is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Assets module.
    """
    api_v1.add_oauth_scope('assets:read', 'Provide access to Assets details')
    api_v1.add_oauth_scope('assets:write', 'Provide write access to Assets details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Asset)
