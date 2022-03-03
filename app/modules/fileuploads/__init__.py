# -*- coding: utf-8 -*-
"""
FileUpload module
============
"""

from app.extensions.api import api_v1
from app.extensions import register_elasticsearch_model

from app.modules import is_module_enabled

if not is_module_enabled('fileuploads'):
    raise RuntimeError('File Uploads is not enabled')


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

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.FileUpload)
