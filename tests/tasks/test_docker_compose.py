# -*- coding: utf-8 -*-
from unittest import mock

from invoke import MockContext

import tasks.docker_compose


def test_rebuild_specific_services():
    with mock.patch('tasks.docker_compose.logger') as logger:
        context = MockContext(
            run={
                'docker-compose rm --stop -f db houston': True,
                'docker volume ls -q -f dangling=true -f name=houston_db* -f name=houston_houston* | xargs docker volume rm': True,
                'docker-compose pull db houston': True,
                'docker-compose build db houston': True,
            },
        )
        tasks.docker_compose.rebuild(context, service=['db', 'houston'])
        assert logger.info.call_args_list == [
            mock.call('Stop and remove codex services db, houston'),
            mock.call('Remove codex volumes db, houston'),
            mock.call('Pull image updates db, houston'),
            mock.call('Rebuild images db, houston'),
            mock.call('You can now do "docker-compose up -d db houston"'),
        ]


def test_rebuild():
    with mock.patch('tasks.docker_compose.logger') as logger:
        context = MockContext(
            run={
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


def test_rebuild_gitlab():
    with mock.patch('tasks.docker_compose.logger') as logger:
        context = MockContext(
            run={
                'docker-compose rm --stop -f gitlab houston': True,
                'docker volume ls -q -f dangling=true -f name=houston_gitlab* -f name=houston_houston* | xargs docker volume rm': True,
                'docker-compose pull gitlab houston': True,
                'docker-compose build gitlab houston': True,
            },
        )
        tasks.docker_compose.rebuild(context, service=['gitlab'])
        assert logger.info.call_args_list == [
            mock.call('Stop and remove codex services gitlab, houston'),
            mock.call('Remove codex volumes gitlab, houston'),
            mock.call('Pull image updates gitlab, houston'),
            mock.call('Rebuild images gitlab, houston'),
            mock.call('You can now do "docker-compose up -d gitlab houston"'),
        ]
