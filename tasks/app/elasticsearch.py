# -*- coding: utf-8 -*-
from tasks.utils import app_context_task


def _get_available_model_mappings():
    from app.extensions import elasticsearch as es

    mapping = {}
    for registered_model in es.REGISTERED_MODELS:
        name = registered_model.__name__
        if name not in mapping:
            mapping[name] = []
        mapping[name].append(registered_model)

    available = {}
    for name in mapping:
        registered_models = mapping[name]
        assert len(registered_models) > 0
        if len(registered_models) == 1:
            registered_model = registered_models[0]
            available[name] = registered_model
        else:
            for registered_model in registered_models:
                unique_name = '%s.%s' % (
                    registered_model.__module__,
                    registered_model.__name__,
                )
                assert unique_name not in available
                available[unique_name] = registered_model

    return available


def _index_worker(model=None, **kwargs):
    from app.extensions import elasticsearch as es

    with es.session.begin(**kwargs):
        if model is None:
            es.es_index_all()
        else:
            available = _get_available_model_mappings()

            model = model.strip()
            model_cls = available.get(model, None)

            if model_cls is None:
                print('Model must be one of %r' % (set(available.keys()),))
            else:
                model_cls.index_all()


def _prune_worker(model=None):
    from app.extensions import elasticsearch as es

    with es.session.begin(blocking=True):
        if model is None:
            es.es_prune_all()
        else:
            available = _get_available_model_mappings()

            model = model.strip()
            model_cls = available.get(model, None)

            if model_cls is None:
                print('Model must be one of %r' % (set(available.keys()),))
            else:
                model_cls.prune_all()


def _invalidate_worker(model=None):
    from app.extensions import elasticsearch as es

    if model is None:
        es.es_invalidate_all()
    else:
        available = _get_available_model_mappings()

        model = model.strip()
        model_cls = available.get(model, None)

        if model_cls is None:
            print('Model must be one of %r' % (set(available.keys()),))
        else:
            model_cls.invalidate_all()


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def status(context, model=None):
    """
    Get the status from Elasticsearch
    """
    from app.extensions import elasticsearch as es
    import utool as ut

    status = es.es_status(missing=True)
    print(ut.repr3(status))


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def index(context, model=None):
    """
    Force index a given model, if specified, otherwise all models
    """
    _index_worker(model=model, forced=True)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def refresh(context, model=None):
    """
    Check the index a given model, if specified, otherwise all models
    """
    _index_worker(model=model, forced=False)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def now(context, model=None):
    """
    Expressly (blocking and forced) index a given model, if specified, otherwise all models
    """
    _index_worker(model=model, blocking=True, forced=True)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def prune(context, model=None):
    """
    Prune (delete) the index for a given model, if specified, otherwise all models
    """
    _prune_worker(model=model)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def invalidate(context, model=None):
    """
    Invalidate all items for a given model, if specified, otherwise all models
    """
    _invalidate_worker(model=model)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def delete_index(context, model=None):
    """
    Delete the index for a given model, if specified, otherwise all models
    """
    from app.extensions import elasticsearch as es

    indices = []

    if model is None:
        indices += es.es_all_indices()
    else:
        available = _get_available_model_mappings()

        model = model.strip()
        model_cls = available.get(model, None)

        if model_cls is None:
            print('Model must be one of %r' % (set(available.keys()),))
        else:
            indices.append(model_cls._index())

    if len(indices) > 0:
        for index in indices:
            print('Deleting ES index %r' % (index,))
            es.es_delete_index(index)
