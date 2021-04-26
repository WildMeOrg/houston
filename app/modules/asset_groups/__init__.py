# -*- coding: utf-8 -*-
"""
Asset_groups module
============
"""

from app.extensions.api import api_v1


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Asset_groups module.
    """
    api_v1.add_oauth_scope('asset_groups:read', 'Provide access to Asset_groups details')
    api_v1.add_oauth_scope(
        'asset_groups:write', 'Provide write access to Asset_groups details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
