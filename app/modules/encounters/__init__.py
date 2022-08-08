# -*- coding: utf-8 -*-
"""
Encounters module
============
"""

from app.extensions import register_elasticsearch_model, register_prometheus_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('encounters'):
    raise RuntimeError('Encounters is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Encounters module.
    """
    api_v1.add_oauth_scope('encounters:read', 'Provide access to Encounters details')
    api_v1.add_oauth_scope(
        'encounters:write', 'Provide write access to Encounters details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Encounter)
    register_prometheus_model(models.Encounter)
