# -*- coding: utf-8 -*-
"""
FileUpload module
============
"""

from app.extensions.api import api_v1


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init FileUploads module.
    """
    api_v1.add_oauth_scope('fileuploads:read', 'Provide access to FileUploads details')
    api_v1.add_oauth_scope(
        'fileuploads:write', 'Provide write access to FileUploads details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
