# -*- coding: utf-8 -*-
"""
Projects module
============
"""

from app.extensions.api import api_v1


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Projects module.
    """
    api_v1.add_oauth_scope('projects:read', 'Provide access to Projects details')
    api_v1.add_oauth_scope('projects:write', 'Provide write access to Projects details')
    api_v1.add_oauth_scope('projects:delete', 'Provide authority to delete Projects')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
