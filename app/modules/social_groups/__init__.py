# -*- coding: utf-8 -*-
"""
Social Groups module
============
"""

from app.extensions.api import api_v1
from app.extensions import register_elasticsearch_model

from app.modules import is_module_enabled

if not is_module_enabled('social_groups'):
    raise RuntimeError('Social Groups is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Social Groups module.
    """
    api_v1.add_oauth_scope(
        'social-groups:read', 'Provide access to Social Groups details'
    )
    api_v1.add_oauth_scope(
        'social-groups:write', 'Provide write access to Social Groups details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.SocialGroup)
