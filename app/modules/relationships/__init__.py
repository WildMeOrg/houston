# -*- coding: utf-8 -*-
"""
Relationships module
============
"""

from app.extensions.api import api_v1


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Relationships module.
    """
    api_v1.add_oauth_scope('relationships:read', 'Provide access to Relationships details')
    api_v1.add_oauth_scope('relationships:write', 'Provide write access to Relationships details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
