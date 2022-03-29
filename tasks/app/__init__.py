# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from config import get_preliminary_config

from tasks.app import (
    assets,
    boilerplates,
    config,
    db,
    dev,
    elasticsearch,
    email,
    endpoints,
    fileuploads,
    initial_development_data,
    job_control,
    audit_logs,
    run,
    shell,
    site_settings,
    swagger,
    users,
)


namespace = Collection(
    assets,
    boilerplates,
    config,
    db,
    dev,
    elasticsearch,
    email,
    endpoints,
    fileuploads,
    initial_development_data,
    job_control,
    audit_logs,
    run,
    shell,
    site_settings,
    swagger,
    users,
)

namespace.configure({'app': {'static_root': get_preliminary_config().STATIC_ROOT}})
