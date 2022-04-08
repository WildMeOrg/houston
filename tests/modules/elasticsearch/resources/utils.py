# -*- coding: utf-8 -*-
"""
elasticsearch resources utils
-------------
"""

PATH = '/api/v1/search/'


def get_mapping_path(module):
    return f'{PATH}app.modules.{module}s.models.{module}/mappings'
