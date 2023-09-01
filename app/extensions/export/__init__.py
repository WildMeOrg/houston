# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Export extension

"""

from flask_restx_patched import is_extension_enabled

if not is_extension_enabled('export'):
    raise RuntimeError('Export is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    from app.extensions.api import api_v1

    """
    Init Passthroughs module.
    """
    api_v1.add_oauth_scope('export:read', 'Provide access to Export API')
    api_v1.add_oauth_scope('export:write', 'Provide write access to Export API')

    # Touch underlying modules
    from . import resources  # NOQA

    api_v1.add_namespace(resources.api)
