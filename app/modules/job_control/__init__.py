# -*- coding: utf-8 -*-
"""
job control module
============
"""


def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Job Control module.
    """
    # Touch underlying modules
    from . import models  # NOQA
