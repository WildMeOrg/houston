# -*- coding: utf-8 -*-
"""
Users module
============
"""

from app.extensions import register_elasticsearch_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('users'):
    raise RuntimeError('Users is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init users module.
    """
    api_v1.add_oauth_scope('users:read', 'Provide access to user details')
    api_v1.add_oauth_scope('users:write', 'Provide write access to user details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.User)
