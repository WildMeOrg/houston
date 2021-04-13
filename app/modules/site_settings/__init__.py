# -*- coding: utf-8 -*-
"""
Site Settings module
============
"""

from app.extensions.api import api_v1


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
