# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from tasks.codex import (
    asset_groups,
    consistency,
    edm,
    encounters,
    initialize,
    integrations,
    organizations,
    collaborations,
    projects,
    run,
)

from config import BaseConfig

namespace = Collection(
    asset_groups,
    consistency,
    edm,
    encounters,
    initialize,
    integrations,
    organizations,
    collaborations,
    projects,
    run,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
