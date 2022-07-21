# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import datetime
import logging
import os

from flask import current_app, url_for
from oauthlib.oauth2 import BackendApplicationClient
from prometheus_client import Counter, Gauge, Info
from prometheus_client.metrics import MetricWrapperBase
from requests_oauthlib import OAuth2Session

from app.extensions.api import api_v1
from flask_restx_patched import is_extension_enabled

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


# Allow non-ssl communication
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

REGISTERED_MODELS = {}
REGISTERED_TAXONOMIES = {}


info = Info(
    'info',
    'Description of the Houston environment',
)

models = Gauge(
    'models',
    'Number of total models by type',
    ['cls'],
)

taxonomies = Gauge(
    'taxonomies',
    'Number of taxonomies by metric',
    ['taxonomy', 'metric'],
)

logins = Gauge(
    'logins',
    'Number of unique users who have logged in over the past specified days',
    ['days'],
)

requests = Counter(
    'requests',
    'Number of total requests by endpoint since start',
    ['method', 'endpoint'],
)

responses = Counter(
    'responses',
    'Number of total responses by endpoint since start',
    ['method', 'endpoint', 'code'],
)

tasks_ = Gauge(
    'tasks',
    'Number of Celery tasks by function',
    ['function'],
)


def register_prometheus_model(cls):
    global REGISTERED_MODELS
    REGISTERED_MODELS[cls] = {
        'status': False,
    }


def _init_info(*args, **kwargs):
    _update_info(*args, **kwargs)


def _init_models(*args, **kwargs):
    _update_models(*args, **kwargs)


def _init_taxonomies(*args, **kwargs):
    pass
    # This function can take a long time, so do not call on init, wait for the background worker to update
    # _update_taxonomies(*args, **kwargs)


def _init_logins(*args, **kwargs):
    _update_logins(*args, **kwargs)


def _init_celery(*args, **kwargs):
    _update_celery(*args, **kwargs)


def _update_info(*args, **kwargs):
    from app import version

    info_dict = {}
    for key, value in version.__dict__.items():
        if key.startswith('__') and key.endswith('__'):
            continue
        info_dict[key] = value

    info.info(info_dict)


def _update_models(*args, **kwargs):
    for cls in REGISTERED_MODELS:
        cls_str = '{}.{}'.format(cls.__module__, cls.__name__)
        value = cls.query.count()
        models.labels(cls=cls_str).set(value)


def _update_taxonomies(*args, **kwargs):
    import tqdm

    from app.modules.encounters.models import Encounter
    from app.modules.individuals.models import Individual

    collector = []

    individuals = Individual.query.all()
    for individual in tqdm.tqdm(individuals, desc='Individuals Taxonomy'):
        collector += individual.get_taxonomy_names()

    individuals_taxonomies = set(collector)
    for taxonomy in sorted(individuals_taxonomies):
        value = collector.count(taxonomy)
        taxonomies.labels(taxonomy=taxonomy, metric='individuals').set(value)

    collector = []

    encounters = Encounter.query.all()
    for encounter in tqdm.tqdm(encounters, desc='Encounters Taxonomy'):
        collector += encounter.get_taxonomy_names()

    encounters_taxonomies = set(collector)
    for taxonomy in sorted(encounters_taxonomies):
        taxonomies.labels(taxonomy=taxonomy, metric='encounters').set(value)

    all_taxonomies = individuals_taxonomies | encounters_taxonomies
    value = len(all_taxonomies)
    taxonomies.labels(taxonomy=None, metric='total').set(value)


def _update_logins(*args, **kwargs):
    from app.modules.auth.models import OAuth2Token

    tokens = OAuth2Token.query.all()
    users = {}
    for token in tokens:
        user_guid = token.user.guid
        created = token.created
        if user_guid is None:
            continue
        if user_guid not in users:
            users[user_guid] = created
        elif users[user_guid] < created:
            users[user_guid] = created

    now = datetime.datetime.utcnow()
    for days in [1, 7, 30, 90, 180, 365, None]:
        if days is None:
            value = len(users)
        else:
            limit = now - datetime.timedelta(days=days)

            value = 0
            for user, timestamp in users.items():
                if timestamp > limit:
                    value += 1

        logins.labels(days=days).set(value)


def _update_celery(*args, **kwargs):
    from flask import current_app

    inspect = current_app.celery.control.inspect()
    stats = inspect.stats()

    if stats is not None:
        functions = {
            None: 0,
        }
        for worker, data in stats.items():
            total = data.get('total', {})
            for function, value in total.items():
                if function not in functions:
                    functions[function] = 0
                functions[function] += value
                functions[None] += value

        for function, value in functions.items():
            tasks_.labels(function=function).set(value)


def _attach_flask_callbacks(app):
    @app.before_request
    def before_request_callback():
        from flask import request

        method = request.method
        endpoint = request.path

        requests.labels(method=method, endpoint=endpoint).inc()

    @app.after_request
    def after_request_callback(response):
        from flask import request

        method = request.method
        endpoint = request.path
        code = response.status_code

        responses.labels(method=method, endpoint=endpoint, code=code).inc()

        return response


def _attach_sqlalchemy_listeners(app):
    from sqlalchemy.event import listen

    global REGISTERED_MODELS

    def _before_insert(mapper, connection, obj):
        try:
            cls = obj.__class__
            cls_str = '{}.{}'.format(cls.__module__, cls.__name__)
            models.labels(cls=cls_str).inc()
        except Exception:  # pragma: no cover
            log.error('Prometheus increment failed for {!r}'.format(obj))
            raise

    def _before_delete(mapper, connection, obj):
        try:
            cls = obj.__class__
            cls_str = '{}.{}'.format(cls.__module__, cls.__name__)
            models.labels(cls=cls_str).dec()
        except Exception:  # pragma: no cover
            log.error('Prometheus decrement failed for {!r}'.format(obj))
            raise

    for cls in REGISTERED_MODELS:
        # Only register this hook once
        if not REGISTERED_MODELS[cls]['status']:
            name = '{}.{}'.format(cls.__module__, cls.__name__)
            log.info('Attach Prometheus listener for {!r}'.format(name))
            listen(cls, 'before_insert', _before_insert, propagate=True)
            listen(cls, 'before_delete', _before_delete, propagate=True)
            REGISTERED_MODELS[cls]['status'] = True


def init(app, *args, **kwargs):
    _attach_flask_callbacks(app)
    _attach_sqlalchemy_listeners(app)

    _init_info(*args, **kwargs)

    _init_models(*args, **kwargs)
    _init_taxonomies(*args, **kwargs)
    _init_logins(*args, **kwargs)

    _init_celery(*args, **kwargs)


def update(*args, **kwargs):
    from app.extensions import prometheus as current_module

    _update_info(*args, **kwargs)

    _update_models(*args, **kwargs)
    _update_taxonomies(*args, **kwargs)
    _update_logins(*args, **kwargs)

    _update_celery(*args, **kwargs)

    samples = []
    for key, value in current_module.__dict__.items():
        if isinstance(value, MetricWrapperBase):
            metrics = value.collect()
            for metric in metrics:
                for sample in metric.samples:
                    samples.append(sample)

    return samples


# Alias with public function
def update_logins(*args, **kwargs):
    _update_logins(*args, **kwargs)


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Prometheus extension initialization point.
    """

    if is_extension_enabled('prometheus'):
        from . import resources

        api_v1.add_oauth_scope('prometheus:read', 'Provide access to Prometheus details')
        api_v1.add_oauth_scope(
            'prometheus:write', 'Provide write access to Prometheus details'
        )

        api_v1.add_namespace(resources.api)

        app.register_blueprint(resources.prometheus)

        log.info('Prometheus metrics available')
    else:
        log.info('Prometheus metrics hidden')


def send_update(data):
    oauth_user = current_app.config.get('OAUTH_USER', None)
    if oauth_user:
        client_id = oauth_user.get('client_id')
        client_secret = oauth_user.get('client_secret')

        token_url = url_for('api.auth_o_auth2_tokens', _external=True)

        client = BackendApplicationClient(
            client_id=client_id, scope=['prometheus:read', 'prometheus:write']
        )
        session = OAuth2Session(client=client)

        session.fetch_token(
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret,
        )

        update_url = url_for('api.prometheus_prometheus_update', _external=True)
        response = session.request('POST', update_url, json=data)
        return response
