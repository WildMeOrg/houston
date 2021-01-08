# -*- coding: utf-8 -*-
# pylint: disable=too-few-public-methods
"""
Permission checking for operations as a common point to share the enum between classes while avoiding
circular dependencies
-----------------------
"""

import enum


class ObjectAccessOperation(enum.Enum):
    READ = 1
    WRITE = 2
    DELETE = 3
