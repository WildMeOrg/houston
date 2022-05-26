# -*- coding: utf-8 -*-
"""
Individuals module
============
"""

from app.extensions import register_elasticsearch_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('individuals'):
    raise RuntimeError('Individuals is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Individuals module.
    """
    api_v1.add_oauth_scope('individuals:read', 'Provide access to Individuals details')
    api_v1.add_oauth_scope(
        'individuals:write', 'Provide write access to Individuals details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Individual)
