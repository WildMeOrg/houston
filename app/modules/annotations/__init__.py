# -*- coding: utf-8 -*-
"""
Annotations module
============
"""

from app.extensions import register_elasticsearch_model, register_prometheus_model
from app.extensions.api import api_v1


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Annotations module.
    """
    from . import models

    api_v1.add_oauth_scope('annotations:read', 'Provide access to Annotations details')
    api_v1.add_oauth_scope(
        'annotations:write', 'Provide write access to Annotations details'
    )
    #
    # # Touch underlying modules
    # from . import models, resources  # NOQA
    #
    # api_v1.add_namespace(resources.api)
    #
    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Annotation)
    register_prometheus_model(models.Annotation)
