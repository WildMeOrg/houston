# -*- coding: utf-8 -*-
"""
Relationships module
============
"""

from app.extensions import register_elasticsearch_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('relationships'):
    raise RuntimeError('Relationships is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Relationships module.
    """
    api_v1.add_oauth_scope(
        'relationships:read', 'Provide access to Relationships details'
    )
    api_v1.add_oauth_scope(
        'relationships:write', 'Provide write access to Relationships details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Relationship)
