# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from config import get_preliminary_config
from tasks.app import run
from tasks.codex import (
    asset_groups,
    collaborations,
    consistency,
    encounters,
    initialize,
    integrations,
    integrity,
    job_control,
    organizations,
    progress,
    projects,
    sightings,
)

namespace = Collection(
    asset_groups,
    collaborations,
    consistency,
    encounters,
    initialize,
    integrations,
    integrity,
    job_control,
    organizations,
    progress,
    projects,
    sightings,
    run,
)

namespace.configure({'app': {'static_root': get_preliminary_config().STATIC_ROOT}})
