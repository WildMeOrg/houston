# -*- coding: utf-8 -*-
"""
job control module
============
"""

from app.extensions.api import api_v1
from app.modules import is_module_enabled

if not is_module_enabled('job_control'):
    raise RuntimeError('Job Control is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Job Control module.
    """

    api_v1.add_oauth_scope('jobs:read', 'Provide access to Job details')
    api_v1.add_oauth_scope('jobs:write', 'Provide write access to Job details')

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)
