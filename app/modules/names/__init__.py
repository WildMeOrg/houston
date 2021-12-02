# -*- coding: utf-8 -*-
"""
Names module
============
"""

from app.extensions.api import api_v1


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
