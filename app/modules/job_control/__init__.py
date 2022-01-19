# -*- coding: utf-8 -*-
"""
job control module
============
"""

from app.modules import is_module_enabled

if not is_module_enabled('job_control'):
    raise RuntimeError('Job Control is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Job Control module.
    """
    # Touch underlying modules
    from . import models  # NOQA
