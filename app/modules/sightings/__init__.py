# -*- coding: utf-8 -*-
"""
Sightings module
============
"""

from app.extensions import register_elasticsearch_model, register_prometheus_model
from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('sightings'):
    raise RuntimeError('Sightings is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Sightings module.
    """
    api_v1.add_oauth_scope('sightings:read', 'Provide access to Sightings details')
    api_v1.add_oauth_scope('sightings:write', 'Provide write access to Sightings details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    # Register Models to use with Elasticsearch
    register_elasticsearch_model(models.Sighting)
    register_prometheus_model(models.Sighting)
