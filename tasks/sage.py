# -*- coding: utf-8 -*-
"""
Application Sage related tasks for Invoke.
"""

from tasks.utils import app_context_task
from flask import current_app
import app
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def _get_available_model_mappings():
    available = {
        'Asset': app.modules.assets.models.Asset,
        'Annotation': app.modules.annotations.models.Annotation,
    }

    return available


def _sync_worker(model=None, **kwargs):
    available = _get_available_model_mappings()

    if model is None:
        for model in available:
            model_cls = available.get(model, None)
            kwargs['skip_asset'] = True  # No need to sync the asset twice
            model_cls.sync_all_with_sage(**kwargs)
    else:
        model = model.strip()
        model_cls = available.get(model, None)

        if model_cls is None:
            print('Model must be one of %r' % (set(available.keys()),))
        else:
            model_cls.sync_all_with_sage(**kwargs)


@app_context_task()
def status(context):
    """Check the status of Sage"""

    current_app.sage.get_status()


@app_context_task()
def results(context):
    """Check and pull the status of Sage jobs"""
    current_app.sage.sync_jobs()


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def sync(context, model=None):
    """
    Sync (push to Sage) the records for a given model, if specified, otherwise all models
    """
    _sync_worker(model=model)
    status(context)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def ensure(context, model=None):
    """
    Check the records for a given model, if specified, otherwise all models
    """
    _sync_worker(model=model, ensure=True)
    status(context)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def force(context, model=None):
    """
    Check the records for a given model, if specified, otherwise all models
    """
    _sync_worker(model=model, ensure=True, force=True, prune=True)
    status(context)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def prune(context, model=None):
    """
    Check the records for a given model, if specified, otherwise all models
    """
    _sync_worker(model=model, ensure=True, prune=True)
    status(context)
