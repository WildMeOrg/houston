# -*- coding: utf-8 -*-
"""
elasticsearch resources utils
-------------
"""

PATH = '/api/v1/search/'


def get_mapping_path(module, testing=True):
    TESTING = 'testing.' if testing else ''
    return f'{PATH}{TESTING}app.modules.{module}s.models.{module}/mappings'
