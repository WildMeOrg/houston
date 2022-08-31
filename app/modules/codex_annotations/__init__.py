# -*- coding: utf-8 -*-
"""
￼Annotations module
￼============
￼"""

from app.extensions import register_elasticsearch_model, register_prometheus_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('codex_annotations'):
    raise RuntimeError('Annotations is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Codex Annotations module.
    """

    # Touch underlying modules

    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.CodexAnnotation)
    register_prometheus_model(models.CodexAnnotation)
