# -*- coding: utf-8 -*-
# This file is meant for celery command lines, for example:
#    celery -A app.extensions.celery.celery worker
import os

from flask import current_app

try:
    celery = current_app.celery
except RuntimeError:
    from .. import create_app

    app = create_app(flask_config_name=os.getenv('FLASK_CONFIG'))
    celery = app.celery


# register celery tasks
