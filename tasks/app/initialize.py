# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""
This file contains initialization tasks to synchronize data from the EDM

You can execute this code via ``invoke app.initialize``
"""
import logging

from ._utils import app_context_task

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@app_context_task
def initialize_edm_admin_user(context):
    """Set up EDM admin user"""
    from flask import current_app

    email = 'admin@example.com'
    password = current_app.config['EDM_AUTHENTICATIONS']['default']['password']
    log.info('Initializing EDM admin user')
    success = current_app.edm.initialize_edm_admin_user(email, password)
    if not success:
        raise RuntimeError('Failed to initialize EDM admin user')
    log.info('Initialized EDM admin user')


@app_context_task
def initialize_users_from_edm(context, edm_authentication=None):
    from app.modules.users.models import User

    User.edm_sync_all()

    context.invoke_execute(context, 'app.consistency.user-staff-permissions')


@app_context_task
def initialize_orgs_from_edm(context, edm_authentication=None):
    from app.modules.organizations.models import Organization

    Organization.edm_sync_all()


@app_context_task
def all(context, edm_authentication=None, skip_on_failure=False):
    log.info('Initializing tasks...')

    try:
        initialize_edm_admin_user(context)
        initialize_users_from_edm(context, edm_authentication=edm_authentication)
        initialize_orgs_from_edm(context, edm_authentication=edm_authentication)
    except AssertionError as exception:
        if not skip_on_failure:
            log.error('%s', exception)
        else:
            log.debug(
                'The following error was ignored due to the `skip_on_failure` flag: %s',
                exception,
            )
            log.info('Running initialize tasks is skipped.')
    else:
        log.info('Initialize tasks successfully applied.')
