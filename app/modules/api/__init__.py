# -*- coding: utf-8 -*-
"""
Houston API registration module
===============================
"""
from app.extensions import api


def init_app(app, **kwargs):
    # Touch underlying modules
    from . import resources

    api.api_v1.add_namespace(resources.api)
