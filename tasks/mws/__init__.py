# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from tasks.mws import (
    consistency,
    initialize,
    integrations,
    run,
)

from config import BaseConfig

namespace = Collection(
    consistency,
    initialize,
    integrations,
    run,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
