# -*- coding: utf-8 -*-
"""
Notifications module
============
"""

from app.extensions.api import api_v1
from app.extensions import register_elasticsearch_model

from app.modules import is_module_enabled

if not is_module_enabled('notifications'):
    raise RuntimeError('Notifications is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Notifications module.
    """
    api_v1.add_oauth_scope(
        'notifications:read', 'Provide access to Notifications details'
    )
    api_v1.add_oauth_scope(
        'notifications:write', 'Provide write access to Notifications details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Notification)
