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
    # Some information needs to be more secure (mostly admin but some other roles (user_manager) occasionally)
    READ_PRIVILEGED = 3
    # internal operations only (only Sage, no wetware users)
    READ_INTERNAL = 4
    # Read where different users see different things, eg lists where admin sees all but researcher sees a limited set
    READ_BY_ROLE = 5
    WRITE = 6
    # internal operations only (only Sage, no wetware users)
    WRITE_INTERNAL = 7
    DELETE = 8
