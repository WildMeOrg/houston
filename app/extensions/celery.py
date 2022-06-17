# -*- coding: utf-8 -*-
# This file is meant for celery command lines, for example:
#    celery -A app.extensions.celery.celery worker
from flask import current_app

from config import get_preliminary_config
from flask_restx_patched import is_extension_enabled, is_module_enabled

config = get_preliminary_config()


try:
    celery = current_app.celery
except RuntimeError:
    from .. import create_app

    app = create_app()
    celery = app.celery

# FIXME: This really needs to be a part of the app creation/loading procedure.
#        As it stands we define modules to load in configuration,
#        but celery is sidelong to that configuration.
#        As such, things like checking for an appliation's context is necessary.

# Register Extension-level tasks

# Always import GitStore tasks
import app.extensions.git_store.tasks  # noqa

if is_extension_enabled('elasticsearch'):
    import app.extensions.elasticsearch.tasks  # noqa

if is_extension_enabled('intelligent_agent'):
    import app.extensions.intelligent_agent.tasks  # noqa

if is_extension_enabled('tus'):
    import app.extensions.tus.tasks  # noqa

if is_extension_enabled('sage'):
    import app.extensions.sage.tasks  # noqa

# Register Module-level tasks

if is_module_enabled('asset_groups'):
    import app.modules.asset_groups.tasks  # noqa

if is_module_enabled('individuals'):
    import app.modules.individuals.tasks  # noqa

if is_module_enabled('job_control'):
    import app.modules.job_control.tasks  # noqa

if is_module_enabled('missions'):
    import app.modules.missions.tasks  # noqa

if is_module_enabled('sightings'):
    import app.modules.sightings.tasks  # noqa
