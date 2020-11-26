# -*- coding: utf-8 -*-
"""
Application Submission management related tasks for Invoke.
"""
from flask import current_app

from ._utils import app_context_task

@app_context_task
def list_submissions(context):
    """
    Show existing submissions.
    """
    from app.modules.submissions.models import Submission

    submissions = Submission.query.all()

    for submission in submissions:
        print("Submission : {} {}".format(submission, submission.assets))

