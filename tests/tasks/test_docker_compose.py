# -*- coding: utf-8 -*-
import pathlib
from unittest import mock

import invoke.exceptions
from invoke import MockContext, Result
import pytest

import tasks.docker_compose
from tests.utils import extension_unavailable


with (pathlib.Path(__file__).parent.parent.parent / 'docker-compose.yml').open() as f:
    DOCKER_COMPOSE = f.read()


def test_rebuild_specific_services():
    with mock.patch('tasks.docker_compose.logger') as logger:
        context = MockContext(
            run={
                'docker-compose config': Result(DOCKER_COMPOSE),
                'docker-compose rm --stop -f db sage': True,
                'docker volume ls -q -f dangling=true -f name=houston_db* -f name=houston_sage* | xargs docker volume rm': True,
                'docker-compose pull db sage': True,
                'docker-compose build db sage': True,
            },
        )
        tasks.docker_compose.rebuild(context, service=['db', 'sage'])
        assert logger.info.call_args_list == [
            mock.call('Stop and remove codex services db, sage'),
            mock.call('Remove codex volumes db, sage'),
            mock.call('Pull image updates db, sage'),
            mock.call('Rebuild images db, sage'),
            mock.call('You can now do "docker-compose up -d db sage"'),
        ]


def test_rebuild():
    with mock.patch('tasks.docker_compose.logger') as logger:
        context = MockContext(
            run={
                'docker-compose config': Result(DOCKER_COMPOSE),
                'docker-compose down --remove-orphans': True,
                'docker volume ls -q -f dangling=true -f name=houston_* | xargs docker volume rm': True,
                'docker-compose pull ': True,
                'docker-compose build ': True,
            },
        )
        tasks.docker_compose.rebuild(context)
        assert logger.info.call_args_list == [
            mock.call('Stop and remove codex services '),
            mock.call('Remove codex volumes '),
            mock.call('Pull image updates '),
            mock.call('Rebuild images '),
            mock.call('You can now do "docker-compose up -d"'),
        ]


@pytest.mark.skipif(extension_unavailable('gitlab'), reason='GitLab extension disabled')
@pytest.mark.requires_local_gitlab
def test_rebuild_gitlab():
    with mock.patch('tasks.docker_compose.logger') as logger:
        context = MockContext(
            run={
                'docker-compose config': Result(DOCKER_COMPOSE),
                'docker-compose rm --stop -f gitlab houston celery_beat celery_worker': True,
                'docker volume ls -q -f dangling=true -f name=houston_gitlab* -f name=houston_houston* -f name=houston_celery_beat* -f name=houston_celery_worker* | xargs docker volume rm': True,
                'docker-compose pull gitlab': True,
                'docker-compose build gitlab houston celery_beat celery_worker': True,
            },
        )
        tasks.docker_compose.rebuild(context, service=['gitlab'])
        assert logger.info.call_args_list == [
            mock.call(
                'Stop and remove codex services gitlab, houston, celery_beat, celery_worker'
            ),
            mock.call('Remove codex volumes gitlab, houston, celery_beat, celery_worker'),
            mock.call('Pull image updates gitlab'),
            mock.call('Rebuild images gitlab, houston, celery_beat, celery_worker'),
            mock.call(
                'You can now do "docker-compose up -d gitlab houston celery_beat celery_worker"'
            ),
        ]


def test_invalid_service():
    with mock.patch('tasks.docker_compose.logger'):
        context = MockContext(
            run={
                'docker-compose config': Result(DOCKER_COMPOSE),
            },
        )
        with pytest.raises(invoke.exceptions.Exit) as exc_info:
            tasks.docker_compose.rebuild(context, service=['invalid'])
        assert exc_info.value.message.startswith(
            'Invalid service "invalid".  Valid services: '
        )
