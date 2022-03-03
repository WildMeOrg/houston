# -*- coding: utf-8 -*-
# This file is meant for celery command lines, for example:
#    celery -A app.extensions.celery.celery worker
from flask import current_app
from flask_restx_patched import is_extension_enabled, is_module_enabled
from config import get_preliminary_config

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
# Register celery tasks

if is_module_enabled('job_control'):
    import app.modules.job_control.tasks  # noqa

if is_module_enabled('asset_groups'):
    import app.modules.asset_groups.tasks  # noqa

if is_module_enabled('sightings'):
    import app.modules.sightings.tasks  # noqa

if is_module_enabled('individuals'):
    import app.modules.individuals.tasks  # noqa

if is_module_enabled('missions'):
    import app.modules.missions.tasks  # noqa

if is_module_enabled('elasticsearch'):
    import app.modules.elasticsearch.tasks  # noqa

if is_extension_enabled('elasticsearch'):
    import app.extensions.elasticsearch.tasks  # noqa
