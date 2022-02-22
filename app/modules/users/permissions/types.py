# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
Permission checking for operations as a common point to share the enums between classes while avoiding
circular dependencies
-----------------------
"""

import enum


class AccessOperation(enum.Enum):
    READ = 1
    # Debug generally only available to staff users so needs a separate category
    READ_DEBUG = 2
    # Some information needs to be much more secure
    READ_PRIVILEGED = 3
    WRITE = 4
    WRITE_PRIVILEGED = 5
    DELETE = 6
