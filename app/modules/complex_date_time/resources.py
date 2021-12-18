# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API ComplexDateTime resources
--------------------------
"""

import logging

from flask import current_app  # NOQA
from flask_login import current_user  # NOQA

from app.extensions.api import Namespace


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'complex_date_time', description='ComplexDateTime'
)  # pylint: disable=invalid-name
