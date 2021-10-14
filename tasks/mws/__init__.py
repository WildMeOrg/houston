# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from tasks.codex import (
    run,
)

from config import BaseConfig

namespace = Collection(
    run,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
