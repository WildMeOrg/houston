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
    # Some information needs to be much more secure
    READ_PRIVILEGED = 2
    WRITE = 3
    DELETE = 4
