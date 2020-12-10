# -*- coding: utf-8 -*-
"""
Application Users management related tasks for Invoke.
"""

from ._utils import app_context_task
import os


@app_context_task(
    help={
        'path': '/path/to/submission/folder/ or /path/to/submission/file.ext',
        'email': 'temp@localhost.  This is the email for the user who will be assigned as the owner of the new submission',
        'description': 'An optional description for the submission',
    }
)
def create_submission_from_path(
    context,
    path,
    email,
    description=None,
):
    """
    Create a new submission via a local file or folder path.

    Command Line:
    > invoke app.submissions.create-submission-from-path --path tests/submissions/test-000/ --email jason@wildme.org
    """
    from app.modules.users.models import User
    from app.modules.submissions.models import Submission, SubmissionMajorType
    from app.extensions import db
    import socket

    user = User.find(email=email)

    if user is None:
        raise Exception("User with email '%s' does not exist." % email)

    absolute_path = os.path.abspath(os.path.expanduser(path))
    print('Attempting to import path: %r' % (absolute_path,))

    if not os.path.exists(path):
        raise IOError('The path %r does not exist.' % (absolute_path,))

    with db.session.begin():
        args = {
            'owner_guid': user.guid,
            'major_type': SubmissionMajorType.filesystem,
            'description': description,
        }
        submission = Submission(**args)
        db.session.add(submission)

    db.session.refresh(submission)

    repo, project = submission.ensure_repository()

    submission.git_copy_path(absolute_path)

    hostname = socket.gethostname()
    submission.git_commit('Initial commit via CLI on host %r' % (hostname,))

    submission.git_push()

    print('Created and pushed new submission: %r' % (submission,))


@app_context_task(
    help={
        'guid': 'A UUID4 for the submission',
        'email': 'temp@localhost.  This is the email for the user who will be assigned as the owner of the new submission',
    }
)
def clone_submission_from_gitlab(
    context,
    guid,
    email,
):
    """
    Clone an existing submission from the external GitLab submission archive

    Command Line:
    > invoke app.submissions.clone-submission-from-gitlab --guid 290950fb-49a8-496a-adf4-e925010f79ce --email jason@wildme.org
    """
    from app.modules.users.models import User
    from app.modules.submissions.models import Submission

    user = User.find(email=email)

    if user is None:
        raise Exception("User with email '%s' does not exist." % email)

    from app import create_app

    app = create_app()
    submission = Submission.query.get(guid)

    if submission is not None:
        print('Submission is already cloned locally:\n\t%s' % (submission,))
        app.sub.ensure_repository(submission)
        return

    submission = app.sub.ensure_submission(guid, owner=user)

    if submission is None:
        raise ValueError('Could not find submission in GitLab using GUID %r' % (guid,))

    print('Cloned submission from GitLab:')
    print('\tSubmission: %r' % (submission,))
    print('\tLocal Path: %r' % (submission.get_absolute_path(),))

@app_context_task
def list_all(context):
    """
    Show existing submissions.
    """
    from app.modules.submissions.models import Submission

    submissions = Submission.query.all()

    for submission in submissions:
        print("Submission : {} {}".format(submission, submission.assets))
