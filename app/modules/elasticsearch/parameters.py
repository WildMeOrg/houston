# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-order
"""
Input arguments (Parameters) for Elasticsearch resources RESTful API
--------------------------------------------------------------------
"""
import logging
from flask_marshmallow import base_fields
from flask_restx_patched import Parameters


log = logging.getLogger(__name__)


class SearchParameters(Parameters):
    """Elasticsearch body paramter"""

    search = base_fields.String(description='An elasticsearch body', required=True)
