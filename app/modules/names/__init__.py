# -*- coding: utf-8 -*-
"""
Names module
============
"""

from app.extensions import register_elasticsearch_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('names'):
    raise RuntimeError('Names is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Names module.
    """
    api_v1.add_oauth_scope('names:read', 'Provide access to Names details')
    api_v1.add_oauth_scope('names:write', 'Provide write access to Names details')
    api_v1.add_oauth_scope('names:delete', 'Provide authority to delete Names')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Name)
