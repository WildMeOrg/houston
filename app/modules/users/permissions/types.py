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
    WRITE = 2
    DELETE = 3
