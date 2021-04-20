# -*- coding: utf-8 -*-
"""
Front-end module
================
"""


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Init front-end module.
    """
    # Touch underlying modules
    from . import backend, frontend

    # Mount front-end routes
    backend.init_app(app)
    frontend.init_app(app)
