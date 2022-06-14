# -*- coding: utf-8 -*-
"""
Autogeneratednames module
============
"""

from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('autogenerated_names'):
    raise RuntimeError('AutogeneratedNames is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init AutogeneratedNames module.
    """
    api_v1.add_oauth_scope(
        'AutogeneratedNames:read', 'Provide access to AutogeneratedNames details'
    )
    api_v1.add_oauth_scope(
        'AutogeneratedNames:write', 'Provide write access to AutogeneratedNames details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
