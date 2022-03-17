# -*- coding: utf-8 -*-
"""
Integrity module
============
"""

from app.extensions.api import api_v1
from app.extensions import register_elasticsearch_model

from app.modules import is_module_enabled

if not is_module_enabled('integrity'):
    raise RuntimeError('Integrity is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Integrity module.
    """
    api_v1.add_oauth_scope('integrity:read', 'Provide access to Integrity details')
    api_v1.add_oauth_scope('integrity:write', 'Provide write access to Integrity details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Integrity)
