# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""
This file contains initialization data for development usage only.

You can execute this code via ``invoke app.consistency``
"""
import logging
import tqdm

from app.extensions import db
from flask import current_app

from ._utils import app_context_task

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@app_context_task
def user_staff_permissions(context):
    from app.modules.users.models import User

    users = User.query.all()

    updated = 0
    with db.session.begin():
        for user in tqdm.tqdm(users):

            update = False

            if not user.in_alpha:
                user.in_alpha = True
                update = True
            if not user.in_beta:
                user.in_beta = True
                update = True

            email = user.email.strip()
            whitlist = [
                'bluemellophone@gmail.com',
                'sito.org+giraffeadmin@gmail.com',
                'sito.org+gstest@gmail.com',
            ]
            is_wildme = email.endswith('@wildme.org') or email in whitlist
            if is_wildme:
                if not user.is_staff:
                    user.is_staff = True
                    update = True
                if not user.is_admin:
                    user.is_admin = True
                    update = True
                print(user)
            else:
                if user.is_staff:
                    user.is_staff = False
                    update = True
                if user.is_admin:
                    user.is_admin = False
                    update = True

            if update:
                db.session.merge(user)
                updated += 1

    print('Updated %d users' % (updated,))


@app_context_task
def cleanup_gitlab(context, dryrun=False):
    import gitlab

    TEST_GROUP_NAMES = ['TEST']
    PER_PAGE = 100
    MAX_PAGES = 100

    remote_uri = current_app.config.get('GITLAB_REMOTE_URI', None)
    remote_personal_access_token = current_app.config.get(
        'GITLAB_REMOTE_LOGIN_PAT', None
    )

    gl = gitlab.Gitlab(
        remote_uri, private_token=remote_personal_access_token
    )
    gl.auth()
    log.info('Logged in: %r' % (gl,))

    projects = []
    groups = gl.groups.list()
    for group in groups:
        if group.name in TEST_GROUP_NAMES:
            page = 1
            log.info('Fetching projects...')
            for page in tqdm.tqdm(range(1, MAX_PAGES + 2), desc='Fetching GitLab Project Pages'):
                projects_page = group.projects.list(per_page=PER_PAGE, page=page)

                if len(projects_page) == 0:
                    log.warn('Reached maximum page: %d' % (page, ))
                    break
                elif page == MAX_PAGES + 1:
                    log.warn('More pages exist that were not processed')
                    break
                projects += projects_page
    log.info('Fetched %d projects' % (len(projects), ))

    if dryrun:
        log.info('[DRYRUN] Would have deleted %d projects for groups %r' % (len(projects), TEST_GROUP_NAMES,))
    else:
        deleted = 0
        for project in tqdm.tqdm(projects, desc='Deleting GitLab Projects'):
            try:
                gl.projects.delete(project.id)
                deleted += 1
            except gitlab.GitlabDeleteError:
                pass
        log.info('Deleted %d / %d projects for groups %r' % (deleted, len(projects), TEST_GROUP_NAMES,))


@app_context_task
def all(context, skip_on_failure=False):
    log.info('Initializing consistency checks...')

    try:
        user_staff_permissions(context)
    except AssertionError as exception:
        if not skip_on_failure:
            log.error('%s', exception)
        else:
            log.debug(
                'The following error was ignored due to the `skip_on_failure` flag: %s',
                exception,
            )
            log.info('Running consistency checks is skipped.')
    else:
        log.info('Consistency checks successfully applied.')
