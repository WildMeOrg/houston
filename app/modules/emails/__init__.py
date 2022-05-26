# -*- coding: utf-8 -*-
"""
Auth module
===========
"""
from app.extensions import register_elasticsearch_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('emails'):
    raise RuntimeError('Emails is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Init email module.
    """
    # Register OAuth scopes
    api_v1.add_oauth_scope('emails:read', 'Provide access to email details')
    api_v1.add_oauth_scope('emails:write', 'Provide write access to email details')

    # Touch underlying modules
    from . import models  # pylint: disable=unused-import  # NOQA

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.EmailRecord)
