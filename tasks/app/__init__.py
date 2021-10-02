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
    email,
    endpoints,
    encounters,
    initialize,
    integrations,
    job_control,
    organizations,
    projects,
    run,
    site_settings,
    asset_groups,
    shell,
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
    email,
    encounters,
    endpoints,
    initialize,
    integrations,
    job_control,
    organizations,
    projects,
    run,
    site_settings,
    asset_groups,
    shell,
    swagger,
    users,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
