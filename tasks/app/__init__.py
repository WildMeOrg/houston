# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from tasks.app import (
    assets,
    fileuploads,
    boilerplates,
    config,
    consistency,
    db,
    dev,
    endpoints,
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
    fileuploads,
    boilerplates,
    config,
    consistency,
    dev,
    db,
    encounters,
    endpoints,
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
