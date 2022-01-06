# -*- coding: utf-8 -*-
"""
Tasks module
============
"""

from app.extensions.api import api_v1


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Tasks module.
    """
    api_v1.add_oauth_scope('tasks:read', 'Provide access to Tasks details')
    api_v1.add_oauth_scope('tasks:write', 'Provide write access to Tasks details')
    api_v1.add_oauth_scope('tasks:delete', 'Provide authority to delete Tasks')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
