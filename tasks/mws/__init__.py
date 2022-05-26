# -*- coding: utf-8 -*-
"""
Application related tasks for Invoke.
"""

from invoke import Collection

from config import get_preliminary_config
from tasks.app import run
from tasks.mws import consistency, initialize, integrations

namespace = Collection(
    consistency,
    initialize,
    integrations,
    run,
)

namespace.configure({'app': {'static_root': get_preliminary_config().STATIC_ROOT}})
