# -*- coding: utf-8 -*-
"""
Social Groups module
============
"""

from app.extensions.api import api_v1


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
