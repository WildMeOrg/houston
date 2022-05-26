# -*- coding: utf-8 -*-
"""
Audit Logs module
============
"""

from app.extensions import register_elasticsearch_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('audit_logs'):
    raise RuntimeError('Audit Logs is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Audit Logs module.
    """
    api_v1.add_oauth_scope('audit_logs:read', 'Provide access to Audit Logs details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.AuditLog)
