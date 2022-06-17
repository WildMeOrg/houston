# -*- coding: utf-8 -*-
import tqdm

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
                unique_name = '{}.{}'.format(
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
                print('Model must be one of {!r}'.format(set(available.keys())))
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
                print('Model must be one of {!r}'.format(set(available.keys())))
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
            print('Model must be one of {!r}'.format(set(available.keys())))
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
    import utool as ut

    from app.extensions import elasticsearch as es

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
            print('Model must be one of {!r}'.format(set(available.keys())))
        else:
            indices.append(model_cls._index())

    if len(indices) > 0:
        for index in indices:
            print('Deleting ES index {!r}'.format(index))
            es.es_delete_index(index)


@app_context_task(
    help={
        'model': 'The name of the model to index',
    }
)
def patch(context, model=None):
    """
    Check the mappings patch for a given model, if specified, otherwise all models
    """
    from app.extensions import elasticsearch as es

    models = []

    available = _get_available_model_mappings()

    if model is None:
        models += [available[key] for key in sorted(available.keys())]
    else:
        model = model.strip()
        model_cls = available.get(model, None)

        if model_cls is None:
            print('Model must be one of {!r}'.format(set(available.keys())))
        else:
            models.append(model_cls)

    custom_schema_mappings = {
        'app.modules.individuals.models.individual.adoptionName': 'get_adoption_name',
        'app.modules.names.models.name.preferring_users': 'get_preferring_users',
        # 'app.modules.sightings.models.sighting.verbatimLocality': 'get_locality',
        # 'app.modules.sightings.models.sighting.taxonomy_guid': 'get_taxonomy_guid',
    }

    if len(models) > 0:
        missing = {}
        for model_cls in models:
            model_index = model_cls._index()
            print('Patching ES model {!r}'.format(model_cls))

            obj = model_cls.query.first()
            if obj is None:
                continue

            with es.session.begin(blocking=True, forced=True):
                obj.index()
            with es.session.begin(blocking=True, forced=True):
                es.es_index_mappings_patch(model_cls)
            with es.session.begin(blocking=True, forced=True):
                obj.index()
            es.es_refresh_index(model_index)

            document = sorted(obj.fetch().get('_source').keys())
            mappings = sorted(es.es_index_mappings(model_index).keys())
            miss_document = set(mappings) - set(document)
            miss_mappings = set(document) - set(mappings)

            if len(miss_document) > 0 or len(miss_mappings) > 0:
                missing[model_cls] = {
                    'obj': obj,
                }
            if len(miss_document) > 0:
                missing[model_cls]['miss_document'] = miss_document
            if len(miss_mappings) > 0:
                missing[model_cls]['miss_mappings'] = miss_mappings

        for model_cls in missing:
            print(model_cls)
            model_index = model_cls._index()

            obj = missing[model_cls].get('obj', None)
            miss_document = missing[model_cls].get('miss_document', None)
            miss_mappings = missing[model_cls].get('miss_mappings', None)

            if miss_document:
                print('\tmissing in document = {!r}'.format(miss_document))

            if miss_mappings:
                print('\tmissing in mappings = {!r}'.format(miss_mappings))
                for miss_mapping in miss_mappings:
                    print(
                        '\t\t{!r}'.format(miss_mapping),
                    )

                    if obj is None:
                        continue

                    custom_mapping = None
                    miss_mapping_str = '{}.{}'.format(model_index, miss_mapping)
                    if miss_mapping_str in custom_schema_mappings:
                        custom_mapping = custom_schema_mappings.get(miss_mapping_str)
                        if not hasattr(obj, custom_mapping):
                            custom_mapping = None

                    if custom_mapping is not None:
                        value_func = getattr(obj, custom_mapping)
                        value = value_func()
                        setattr(obj, miss_mapping, value)

                    if hasattr(obj, miss_mapping):
                        value = getattr(obj, miss_mapping)
                        if value is None or (isinstance(value, list) and len(value) == 0):
                            candidates = model_cls.query.all()
                            for candidate in tqdm.tqdm(candidates, desc='Searching'):
                                if candidate is None:
                                    continue

                                if custom_mapping is not None:
                                    value_func = getattr(candidate, custom_mapping)
                                    value = value_func()
                                    setattr(candidate, miss_mapping, value)

                                if hasattr(candidate, miss_mapping):
                                    value_ = getattr(candidate, miss_mapping)
                                    if value != value_:
                                        print(
                                            '\t\tfound non-empty candidate for attribute {!r}: {!r}, indexing now'.format(
                                                miss_mapping, value_
                                            )
                                        )
                                        with es.session.begin(blocking=True, forced=True):
                                            candidate.index()
                                        with es.session.begin(blocking=True, forced=True):
                                            es.es_index_mappings_patch(model_cls)
                                        with es.session.begin(blocking=True, forced=True):
                                            candidate.index()
                                        es.es_refresh_index(model_index)
                                        break
                        else:
                            print('search: unprocessable value: {!r}'.format(value))
                    else:
                        print('search: unmappable value: {!r}'.format(value))
