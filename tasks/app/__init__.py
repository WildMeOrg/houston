# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from config import get_preliminary_config
from tasks.app import (
    assets,
    audit_logs,
    boilerplates,
    config,
    db,
    elasticsearch,
    email,
    endpoints,
    fileuploads,
    initial_development_data,
    run,
    shell,
    site_settings,
    swagger,
    tus,
    users,
)

namespace = Collection(
    assets,
    boilerplates,
    config,
    db,
    elasticsearch,
    email,
    endpoints,
    fileuploads,
    initial_development_data,
    audit_logs,
    run,
    shell,
    site_settings,
    swagger,
    tus,
    users,
)

namespace.configure({'app': {'static_root': get_preliminary_config().STATIC_ROOT}})
