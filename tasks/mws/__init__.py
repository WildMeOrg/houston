# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from tasks.app import run
from tasks.mws import (
    consistency,
    initialize,
    integrations,
)

from config import BaseConfig

namespace = Collection(
    consistency,
    initialize,
    integrations,
    run,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
