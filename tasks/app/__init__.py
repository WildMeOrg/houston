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
    edm,
    endpoints,
    env,
    encounters,
    initialize,
    integrations,
    organizations,
    projects,
    run,
    site_settings,
    asset_groups,
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
    edm,
    encounters,
    endpoints,
    env,
    initialize,
    integrations,
    organizations,
    projects,
    run,
    site_settings,
    asset_groups,
    swagger,
    users,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
