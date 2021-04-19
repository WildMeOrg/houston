# -*- coding: utf-8 -*-
"""
Application dependencies related tasks for Invoke.
"""
import logging

from invoke import task


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@task
def install_python_dependencies(context, force=False):
    """
    Install Python dependencies listed in requirements.txt.
    """
    log.info('Installing project dependencies...')
    context.run('pip install %s -e .' % ('--upgrade' if force else ''))
    log.info('Project dependencies are installed.')


@task
def install_swagger_ui(context, force=False):
    # pylint: disable=unused-argument
    """
    Install Swagger UI HTML/JS/CSS assets.
    """
    log.info('Installing Swagger UI assets...')
    context.run('bash scripts/build.swagger-ui.sh')
    log.info('Swagger UI is installed.')


@task
def install(context):
    # pylint: disable=unused-argument
    """
    Install project dependencies.
    """
    install_python_dependencies(context)
    # install_swagger_ui(context)
