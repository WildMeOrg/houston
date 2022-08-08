# -*- coding: utf-8 -*-
"""
Collaborations module
============
"""

from app.extensions import register_elasticsearch_model, register_prometheus_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('collaborations'):
    raise RuntimeError('Collaborations is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Collaborations module.
    """
    api_v1.add_oauth_scope(
        'collaborations:read', 'Provide access to Collaborations details'
    )
    api_v1.add_oauth_scope(
        'collaborations:write', 'Provide write access to Collaborations details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Collaboration)
    register_prometheus_model(models.Collaboration)
