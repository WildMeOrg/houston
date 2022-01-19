# -*- coding: utf-8 -*-
"""
Configuration module
=============
"""

from app.extensions.api import api_v1

from app.modules import is_module_enabled

if not is_module_enabled('configuration'):
    raise RuntimeError('Configuration is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Configuration module.
    """
    api_v1.add_oauth_scope('configuration:read', 'Provide access to (EDM) configuration')
    api_v1.add_oauth_scope(
        'configuration:write', 'Provide write access to (EDM) configuration'
    )

    # Touch underlying modules
    from . import resources  # NOQA

    api_v1.add_namespace(resources.edm_configuration)
    api_v1.add_namespace(resources.edm_configurationDefinition)
