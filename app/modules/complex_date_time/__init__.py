# -*- coding: utf-8 -*-
"""
ComplexDateTime module
============
"""

from app.extensions.api import api_v1

from app.modules import is_module_enabled

if not is_module_enabled('complex_date_time'):
    raise RuntimeError('Complex DateTime is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init ComplexDateTime module.
    """
    api_v1.add_oauth_scope(
        'complex_date_time:read', 'Provide access to ComplexDateTime details'
    )
    api_v1.add_oauth_scope(
        'complex_date_time:write', 'Provide write access to ComplexDateTime details'
    )
    api_v1.add_oauth_scope(
        'complex_date_time:delete', 'Provide authority to delete ComplexDateTime'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
