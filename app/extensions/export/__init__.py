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

    """
    Init Passthroughs module.
    """
    # issue #932 removes export permission entirely
    # api_v1.add_oauth_scope('export:read', 'Provide access to Export API')
    # api_v1.add_oauth_scope('export:write', 'Provide write access to Export API')
