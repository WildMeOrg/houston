# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Intelligent Agent Extension

"""


from flask_restx_patched import is_extension_enabled

if not is_extension_enabled('intelligent_agent'):
    raise RuntimeError('IntelligentAgent is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument

    pass

    # from . import models, tasks  # NOQA
