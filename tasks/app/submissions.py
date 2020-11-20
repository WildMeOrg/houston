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
