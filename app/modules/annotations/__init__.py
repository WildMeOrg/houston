# -*- coding: utf-8 -*-
"""
Annotations module
============
"""

from app.extensions.api import api_v1
from app.extensions import register_elasticsearch_model

from app.modules import is_module_enabled

if not is_module_enabled('annotations'):
    raise RuntimeError('Annotations is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Annotations module.
    """
    api_v1.add_oauth_scope('annotations:read', 'Provide access to Annotations details')
    api_v1.add_oauth_scope(
        'annotations:write', 'Provide write access to Annotations details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Annotation)
