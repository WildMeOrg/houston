# -*- coding: utf-8 -*-
"""
docker-compose tasks for invoke
"""
import logging

from invoke import task
from invoke.exceptions import Exit
import yaml


logger = logging.getLogger(__name__)


@task
def rebuild(context, service=[]):
    docker_compose_config = context.run('docker-compose config', hide='out')
    config = yaml.safe_load(docker_compose_config.stdout)
    for s in service:
        if s not in config['services']:
            raise Exit(
                f'Invalid service "{s}".  Valid services: {", ".join(config["services"])}'
            )
    if 'gitlab' in service and 'houston' not in service:
        service.append('houston')
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
    pull_services = []
    if service:
        # Only pull if "build" is not specified
        pull_services = [s for s in service if not config['services'][s].get('build')]
    logger.info(f'Pull image updates {", ".join(pull_services)}')
    context.run(f'docker-compose pull {" ".join(pull_services)}', echo=True)
    logger.info(f'Rebuild images {services_}')
    context.run(f'docker-compose build {" ".join(services)}', echo=True)
    command = ['docker-compose', 'up', '-d'] + services
    logger.info(f'You can now do "{" ".join(command)}"')
