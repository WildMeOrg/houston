# -*- coding: utf-8 -*-
"""
Site Settings module
============
"""

from app.extensions import register_prometheus_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('site_settings'):
    raise RuntimeError('Site Settings is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Site Settings module.
    """
    api_v1.add_oauth_scope(
        'site-settings:read', 'Provide access to Site Settings details'
    )
    api_v1.add_oauth_scope(
        'site-settings:write', 'Provide write access to Site Settings details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
    register_prometheus_model(models.Taxonomy)
