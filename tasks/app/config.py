# -*- coding: utf-8 -*-
"""
Application HoustonConfig management related tasks for Invoke.
"""

from ._utils import app_context_task


@app_context_task(
    help={
        'key': 'The Flask config key you wish to override, see values in config.py and _db/secrets.py',
        'value': 'A JSON-serializable value',
    }
)
def set(
    context,
    key,
    value,
):
    """
    Create a new database configuration override
    """
    from app.extensions.config.models import HoustonConfig

    HoustonConfig.set(key, value)


@app_context_task(
    help={
        'key': 'The Flask config key you wish to override, see values in config.py and _db/secrets.py',
    }
)
def forget(
    context,
    key,
):
    """
    Forget a new database configuration override
    """
    from app.extensions.config.models import HoustonConfig

    HoustonConfig.forget(key)


@app_context_task
def list(context):
    """
    Show existing Houston database configurations.
    """
    from app.extensions.config.models import HoustonConfig

    houston_configs = HoustonConfig.query.all()

    for houston_config in houston_configs:
        print('{}'.format(houston_config))
