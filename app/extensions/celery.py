# -*- coding: utf-8 -*-
# This file is meant for celery command lines, for example:
#    celery -A app.extensions.celery.celery worker
from flask import current_app
from flask_restx_patched import is_module_enabled

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
import app.modules.asset_groups.tasks  # noqa
import app.modules.job_control.tasks  # noqa
import app.modules.sightings.tasks  # noqa
import app.modules.individuals.tasks  # noqa

if is_module_enabled('elasticsearch'):
    import app.modules.elasticsearch.tasks  # noqa
