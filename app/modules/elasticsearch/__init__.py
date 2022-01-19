# -*- coding: utf-8 -*-

from app.modules import is_module_enabled

if not is_module_enabled('elasticsearch'):
    raise RuntimeError('Elastic Search is not enabled')


def init_app(app, **kwargs):
    pass
