# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from config import get_preliminary_config

from tasks.app import run
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
    elasticsearch,
    sightings,
)


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
    elasticsearch,
    sightings,
    run,
)

namespace.configure({'app': {'static_root': get_preliminary_config().STATIC_ROOT}})
