# -*- coding: utf-8 -*-
"""
docker-compose tasks for invoke
"""
import logging

from invoke import task


logger = logging.getLogger(__name__)


@task
def rebuild(context, service=[]):
    services = service
    services_ = ', '.join(services)
    logger.info(f'Stop and remove codex services {services_}')
    if services:
        context.run(f'docker-compose rm --stop -f {" ".join(services)}', echo=True)
    else:
        context.run('docker-compose down --remove-orphans', echo=True)
    logger.info(f'Remove codex volumes {services_}')
    name_filter = '-f name=houston_*'
    if services:
        name_filter = ' '.join(f'-f name=houston_{service}*' for service in services)
    context.run(
        f'docker volume ls -q -f dangling=true {name_filter} | xargs docker volume rm',
        echo=True,
        warn=True,
    )
    logger.info(f'Pull image updates {services_}')
    context.run(f'docker-compose pull {" ".join(services)}', echo=True)
    logger.info(f'Rebuild images {services_}')
    context.run(f'docker-compose build {" ".join(services)}', echo=True)
    command = ['docker-compose', 'up', '-d'] + services
    logger.info(f'You can now do "{" ".join(command)}"')


@task
def rebuild_gitlab(context):
    rebuild(context, service=['gitlab', 'houston'])
