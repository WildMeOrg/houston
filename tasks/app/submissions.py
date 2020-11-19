# -*- coding: utf-8 -*-
"""
Application Submission management related tasks for Invoke.
"""
from flask import current_app
from app.extensions.submission import SubmissionManager
from ._utils import app_context_task

@app_context_task
def list_submissions(context):
    """
    Show existing submissions.
    """
    from app.modules.submissions.models import Submission

    submissions = Submission.query.all()

    for submission in submissions:
        print("Submission : {} ".format(submission))

@app_context_task(help={'guid': '1234-4567-7890-1234'})
def clone_submission(context, submission_guid):
    """
    Clone submission by UUID.
    """
    current_app.sub.ensure_submission(submission_guid)

