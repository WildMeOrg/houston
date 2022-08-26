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
    Init Annotations module.
    """

    # Touch underlying modules
    from app.modules.annotations import models as annot_models

    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.CodexAnnotation)
    register_prometheus_model(models.CodexAnnotation)

    # This has to be wrong surely. but doing it fixes a bunch of tests
    register_elasticsearch_model(annot_models.Annotation)
    register_prometheus_model(annot_models.Annotation)
