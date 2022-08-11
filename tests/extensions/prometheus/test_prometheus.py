# -*- coding: utf-8 -*-
import datetime
import re
from unittest import mock

import pytest

from app.extensions.prometheus import (
    _update_celery,
    _update_info,
    _update_logins,
    _update_taxonomies,
    init,
)
from tests.utils import module_unavailable


def test_update_info(request):
    info_patch = mock.patch('app.extensions.prometheus.info')
    info = info_patch.start()
    request.addfinalizer(info_patch.stop)

    _update_info()

    info_dict = info.info.call_args[0][0]
    assert re.match('[0-9a-f.+]+$', info_dict['version'])
    assert re.match('[0-9a-f.]+$', info_dict['git_revision'])
    assert re.match('[0-9a-f.+]+$', info_dict['full_version'])


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_update_taxonomies(request):
    taxonomies_patch = mock.patch('app.extensions.prometheus.taxonomies')
    taxonomies = taxonomies_patch.start()
    request.addfinalizer(taxonomies_patch.stop)

    individual_patch = mock.patch('app.modules.individuals.models.Individual')
    Individual = individual_patch.start()
    request.addfinalizer(individual_patch.stop)

    encounter_patch = mock.patch('app.modules.encounters.models.Encounter')
    Encounter = encounter_patch.start()
    request.addfinalizer(encounter_patch.stop)

    individuals = [mock.Mock(), mock.Mock(), mock.Mock()]
    individuals[0].get_taxonomy_names.return_value = []
    individuals[1].get_taxonomy_names.return_value = [
        'Hybrid zebra',
        'Equus grevyi',
        'Equus grevyi',
    ]
    individuals[2].get_taxonomy_names.return_value = [
        'Equus grevyi',
        'Plains zebra',
    ]
    Individual.query.all.return_value = individuals

    encounters = [mock.Mock()]
    encounters[0].get_taxonomy_names.return_value = ['Hybrid zebra', 'Other']
    Encounter.query.all.return_value = encounters

    taxonomy_mocks = {}

    def taxonomies_labels(**kwargs):
        sorted_args = str({k: kwargs[k] for k in sorted(kwargs)})
        return taxonomy_mocks.setdefault(sorted_args, mock.Mock(**kwargs))

    taxonomies.labels.side_effect = taxonomies_labels

    _update_taxonomies()

    for i, (taxonomy, metric, count) in enumerate(
        [
            ('Equus grevyi', 'individuals', 3),
            ('Hybrid zebra', 'individuals', 1),
            ('Plains zebra', 'individuals', 1),
            ('Hybrid zebra', 'encounters', 1),
            ('Other', 'encounters', 1),
            (None, 'total', 4),
        ]
    ):
        assert taxonomies.labels.call_args_list[i] == mock.call(
            taxonomy=taxonomy, metric=metric
        )
        assert taxonomies.labels(taxonomy=taxonomy, metric=metric).set.call_args_list == [
            mock.call(count)
        ]


def test_update_logins(request):
    logins_patch = mock.patch('app.extensions.prometheus.logins')
    logins = logins_patch.start()
    request.addfinalizer(logins_patch.stop)

    oauth2token_patch = mock.patch('app.modules.auth.models.OAuth2Token')
    OAuth2Token = oauth2token_patch.start()
    request.addfinalizer(oauth2token_patch.stop)

    now = datetime.datetime.utcnow()
    datetime_patch = mock.patch('app.extensions.prometheus.datetime.datetime')
    datetime_patch.start().utcnow.return_value = now
    request.addfinalizer(datetime_patch.stop)

    user1 = mock.Mock(guid='153b4b7b-12b5-46d5-a1c1-1de28aad747c')
    user2 = mock.Mock(guid='ba89f346-056c-426d-8cb9-18c9919ab852')
    user3 = mock.Mock(guid='168cca2d-9d7f-4ce7-a343-c6ad6e5f4b4c')
    OAuth2Token.query.all.return_value = [
        mock.Mock(user=user1, created=now),
        mock.Mock(user=user1, created=now - datetime.timedelta(days=3)),
        mock.Mock(user=user1, created=now - datetime.timedelta(days=4)),
        mock.Mock(user=user2, created=now - datetime.timedelta(days=4)),
        mock.Mock(user=user1, created=now - datetime.timedelta(days=20)),
        mock.Mock(user=user3, created=now - datetime.timedelta(days=400)),
    ]

    logins_count = {}

    def logins_labels(**kwargs):
        sorted_kwargs = str({k: kwargs[k] for k in sorted(kwargs)})
        return logins_count.setdefault(sorted_kwargs, mock.Mock(**kwargs))

    logins.labels.side_effect = logins_labels

    _update_logins()

    for i, (days, count) in enumerate(
        (
            (1, 1),  # user1's latest login
            (7, 2),  # user1 and user2's latest login
            (30, 2),
            (90, 2),
            (180, 2),
            (365, 2),
            (None, 3),
        )
    ):
        assert logins.labels.call_args_list[i] == mock.call(days=days)
        assert logins.labels(days=days).set.call_args_list == [mock.call(count)]


def test_update_celery(request):
    tasks_patch = mock.patch('app.extensions.prometheus.tasks_')
    tasks_ = tasks_patch.start()
    request.addfinalizer(tasks_patch.stop)

    current_app_patch = mock.patch('flask.current_app')
    current_app = current_app_patch.start()
    request.addfinalizer(current_app_patch.stop)

    current_app.celery.control.inspect().stats.return_value = None

    tasks_count = {}

    def tasks_labels(**kwargs):
        sorted_kwargs = str({k: kwargs[k] for k in sorted(kwargs)})
        return tasks_count.setdefault(sorted_kwargs, mock.Mock(**kwargs))

    tasks_.labels.side_effect = tasks_labels

    _update_celery()

    assert not tasks_.labels.called

    tasks_.label.reset_mock()

    current_app.celery.control.inspect().stats.return_value = {
        'celery@2a56fc477be1': {
            'total': {
                'app.extensions.elasticsearch.tasks.es_task_refresh_index_all': 52,
                'app.extensions.elasticsearch.tasks.es_task_invalidate_indexed_timestamps': 5,
                'app.extensions.sage.tasks.sage_task_jobs_sync': 573,
                'app.extensions.elasticsearch.tasks.es_task_index_bulk': 97,
                'app.extensions.git_store.tasks.ensure_remote': 25,
                'app.extensions.intelligent_agent.tasks.twitterbot_collect': 6178,
                'app.modules.asset_groups.tasks.sage_detection': 1,
                'app.modules.asset_groups.tasks.fetch_sage_detection_result': 1,
                'app.extensions.elasticsearch.tasks.es_task_delete_guid_bulk': 3,
                'app.extensions.tus.tasks.tus_task_cleanup': 195,
            },
            'pid': 1,
            'clock': '1574972',
            'uptime': 511767,
            'pool': {'max-concurrency': 8},
            'broker': {
                'hostname': 'redis',
                'userid': None,
                'virtual_host': '1',
                'port': 6379,
                'insist': False,
                'ssl': False,
                'transport': 'redis',
                'connect_timeout': None,
                'transport_options': {},
                'login_method': None,
                'uri_prefix': None,
                'heartbeat': 120.0,
                'failover_strategy': 'round-robin',
                'alternates': [],
            },
            'prefetch_count': 222,
            'rusage': {
                'utime': 87106.079407,
                'stime': 3286.331366,
                'maxrss': 8645272,
                'ixrss': 0,
                'idrss': 0,
                'isrss': 0,
                'minflt': 13857232,
                'majflt': 128792,
                'nswap': 0,
                'inblock': 4252112,
                'oublock': 0,
                'msgsnd': 0,
                'msgrcv': 0,
                'nsignals': 0,
                'nvcsw': 121582900,
                'nivcsw': 2319838,
            },
        },
        'celery@2216a70b5470': {
            'total': {
                'app.extensions.intelligent_agent.tasks.twitterbot_collect': 5787,
                'app.extensions.elasticsearch.tasks.es_task_index_bulk': 140,
                'app.extensions.sage.tasks.sage_task_jobs_sync': 584,
                'app.extensions.git_store.tasks.ensure_remote': 34,
                'app.extensions.tus.tasks.tus_task_cleanup': 172,
                'app.extensions.git_store.tasks.git_commit': 3,
                'app.modules.sightings.tasks.send_all_identification': 4,
                'app.extensions.elasticsearch.tasks.es_task_delete_guid_bulk': 2,
                'app.modules.asset_groups.tasks.sage_detection': 2,
                'app.modules.asset_groups.tasks.fetch_sage_detection_result': 2,
                'app.extensions.git_store.tasks.git_push': 2,
                'app.extensions.elasticsearch.tasks.es_task_refresh_index_all': 50,
                'app.extensions.elasticsearch.tasks.es_task_invalidate_indexed_timestamps': 4,
            },
            'pid': 1,
            'clock': '1574972',
            'uptime': 511767,
            'pool': {'max-concurrency': 8},
            'broker': {
                'hostname': 'redis',
                'userid': None,
                'virtual_host': '1',
                'port': 6379,
                'insist': False,
                'ssl': False,
                'transport': 'redis',
                'connect_timeout': None,
                'transport_options': {},
                'login_method': None,
                'uri_prefix': None,
                'heartbeat': 120.0,
                'failover_strategy': 'round-robin',
                'alternates': [],
            },
            'prefetch_count': 227,
            'rusage': {
                'utime': 93172.318754,
                'stime': 3613.843238,
                'maxrss': 9949900,
                'ixrss': 0,
                'idrss': 0,
                'isrss': 0,
                'minflt': 20286171,
                'majflt': 275882,
                'nswap': 0,
                'inblock': 5301192,
                'oublock': 48,
                'msgsnd': 0,
                'msgrcv': 0,
                'nsignals': 0,
                'nvcsw': 129023555,
                'nivcsw': 2458293,
            },
        },
    }

    _update_celery()

    for i, (function, count) in enumerate(
        (
            (None, 13916),
            ('app.extensions.elasticsearch.tasks.es_task_refresh_index_all', 102),
            (
                'app.extensions.elasticsearch.tasks.es_task_invalidate_indexed_timestamps',
                9,
            ),
            ('app.extensions.sage.tasks.sage_task_jobs_sync', 1157),
            ('app.extensions.elasticsearch.tasks.es_task_index_bulk', 237),
            ('app.extensions.git_store.tasks.ensure_remote', 59),
            ('app.extensions.intelligent_agent.tasks.twitterbot_collect', 11965),
            ('app.modules.asset_groups.tasks.sage_detection', 3),
            ('app.modules.asset_groups.tasks.fetch_sage_detection_result', 3),
            ('app.extensions.elasticsearch.tasks.es_task_delete_guid_bulk', 5),
            ('app.extensions.tus.tasks.tus_task_cleanup', 367),
            ('app.extensions.git_store.tasks.git_commit', 3),
            ('app.modules.sightings.tasks.send_all_identification', 4),
            ('app.extensions.git_store.tasks.git_push', 2),
        )
    ):
        assert tasks_.labels.call_args_list[i] == mock.call(function=function)
        assert tasks_.labels(function=function).set.call_args == mock.call(count)


def test_init(request):
    patches = []
    functions = {}
    for path in (
        'app.extensions.prometheus._attach_flask_callbacks',
        'app.extensions.prometheus._attach_sqlalchemy_listeners',
        'app.extensions.prometheus._update_info',
        'app.extensions.prometheus._update_models',
        'app.extensions.prometheus._update_taxonomies',
        'app.extensions.prometheus._update_logins',
    ):
        patches.append(mock.patch(path))
        functions[path.rsplit('.', 1)[-1]] = patches[-1].start()

    request.addfinalizer(lambda: [patch.stop() for patch in patches])

    app = mock.Mock()
    init(app, 'a', b='c')

    assert functions['_attach_flask_callbacks'].call_count == 1
    assert functions['_attach_flask_callbacks'].call_args == mock.call(app)
    assert functions['_attach_sqlalchemy_listeners'].call_count == 1
    assert functions['_attach_sqlalchemy_listeners'].call_args == mock.call(app)
    assert functions['_update_info'].call_count == 1
    assert functions['_update_info'].call_args == mock.call('a', b='c')
    assert functions['_update_models'].call_count == 1
    assert functions['_update_models'].call_args == mock.call('a', b='c')
    assert not functions['_update_taxonomies'].called
    assert functions['_update_logins'].call_count == 1
    assert functions['_update_logins'].call_args == mock.call('a', b='c')
