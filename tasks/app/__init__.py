# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from tasks.app import (
    assets,
    boilerplates,
    config,
    db,
    dev,
    email,
    endpoints,
    fileuploads,
    initial_development_data,
    job_control,
    shell,
    site_settings,
    swagger,
    users,
)

from config import BaseConfig

namespace = Collection(
    assets,
    boilerplates,
    config,
    db,
    dev,
    email,
    endpoints,
    fileuploads,
    initial_development_data,
    job_control,
    shell,
    site_settings,
    swagger,
    users,
)

namespace.configure({'app': {'static_root': BaseConfig.STATIC_ROOT}})
