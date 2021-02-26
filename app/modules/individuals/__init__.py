# -*- coding: utf-8 -*-
"""
Individuals module
============
"""

from app.extensions.api import api_v1


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Individuals module.
    """
    api_v1.add_oauth_scope('individuals:read', 'Provide access to Individuals details')
    api_v1.add_oauth_scope(
        'individuals:write', 'Provide write access to Individuals details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
