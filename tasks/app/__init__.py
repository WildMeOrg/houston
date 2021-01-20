# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from tasks.app import (
    assets,
    boilerplates,
    config,
    consistency,
    db,
    dependencies,
    dev,
    env,
    encounters,
    initialize,
    organizations,
    projects,
    run,
    submissions,
    swagger,
    users,
)

from config import BaseConfig

namespace = Collection(
    assets,
    boilerplates,
    config,
    consistency,
    dependencies,
    dev,
    db,
    encounters,
    env,
    initialize,
    organizations,
    projects,
    run,
    submissions,
    swagger,
    users,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
