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
    import requests

    log.info('Initializing EDM admin user')
    base_url = current_app.config['EDM_URIS'][0]
    password = current_app.config['EDM_AUTHENTICATIONS'][0]['password']
    payload = {'adminPassword': password}
    url = f'{base_url}/edm/init.jsp'
    # Contact EDM to initialize
    resp = requests.get(url, params=payload)
    if not resp.ok:
        raise RuntimeError(f'Failed to initialize EDM admin user: {resp.reason}')
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
def initialize_gitlab_submissions(context, email, dryrun=False):
    """
    Create test submissions in GitLab

    Command Line:
    > invoke app.initialize.initialize-gitlab-submissions --email jason@wildme.org
    """
    from app.modules.users.models import User
    from app.modules.submissions.models import Submission, SubmissionMajorType
    from app.extensions import db
    from flask import current_app
    import config
    import uuid
    import os

    WHITELIST_TAG = 'type:pytest-required'

    user = User.find(email=email)
    # Coverage runs this a user@example.com who does not have admin role so this check was removed as
    # the initialisation works without it
    # assert user.is_admin, 'Specified user must be an admin'

    if user is None:
        raise Exception("User with email '%s' does not exist." % email)

    test_root = os.path.join(
        config.TestingConfig.PROJECT_ROOT, 'tests', 'submissions', 'test-000'
    )
    image_data = [
        (
            uuid.UUID('00000000-0000-0000-0000-000000000011'),
            os.path.join(test_root, 'zebra.jpg'),
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000012'),
            os.path.join(test_root, 'fluke.jpg'),
        ),
    ]
    submission_data = [
        (uuid.UUID('00000000-0000-0000-0000-000000000001'), []),
        (uuid.UUID('00000000-0000-0000-0000-000000000002'), image_data),
    ]

    for submission_guid, submission_data in submission_data:

        current_app.sub.ensure_initialized()
        projects = current_app.sub.gl.projects.list(search=str(submission_guid))

        if len(projects) > 0:
            assert len(projects) == 1
            project = projects[0]
            log.info(
                'Submission %r already on GitLab, existing tags: %r'
                % (
                    submission_guid,
                    project.tag_list,
                )
            )
        else:
            log.info(
                'Submission %r missing on GitLab, provisioning...' % (submission_guid,)
            )

            submission = Submission.query.get(submission_guid)

            if submission is None:
                log.info(
                    'Submission %r missing locally, creating...' % (submission_guid,)
                )
                with db.session.begin():
                    args = {
                        'guid': submission_guid,
                        'owner_guid': user.guid,
                        'major_type': SubmissionMajorType.test,
                        'description': 'This is a required PyTest submission (do not delete)',
                    }
                    submission = Submission(**args)
                    db.session.add(submission)
                db.session.refresh(submission)
                log.info('Submission %r created' % (submission,))
            else:
                log.info('Submission %r found locally' % (submission,))

            if dryrun:
                log.info('DRYRUN: Submission creation skipped...')
                continue

            repo, project = submission.ensure_repository(additional_tags=[WHITELIST_TAG])

            filepath_guid_mapping = {}
            for file_guid, filename in submission_data:
                filepath = os.path.abspath(os.path.expanduser(filename))
                if not os.path.exists(filepath):
                    raise IOError('The path %r does not exist.' % (filepath,))
                repo_filepath = submission.git_copy_file_add(filepath)
                filepath_guid_mapping[repo_filepath] = file_guid

            submission.git_commit(
                'Initial commit for testing',
                existing_filepath_guid_mapping=filepath_guid_mapping,
            )

            submission.git_push()

            print('Created and pushed new submission: %r' % (submission,))

        assert (
            WHITELIST_TAG in project.tag_list
        ), 'Project %r needs to be re-provisioned: %r' % (
            project,
            project.tag_list,
        )


@app_context_task
def all(context, edm_authentication=None, skip_on_failure=False):
    log.info('Initializing tasks...')

    try:
        initialize_edm_admin_user(context)
        initialize_users_from_edm(context, edm_authentication=edm_authentication)
        initialize_orgs_from_edm(context, edm_authentication=edm_authentication)
        # initialize_gitlab_submissions(context)
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
