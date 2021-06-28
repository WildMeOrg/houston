# -*- coding: utf-8 -*-
"""
Application EDM related tasks for Invoke.
"""

from ._utils import app_context_task


@app_context_task()
def print_jobs(context):
    """Print out all of the outstanding job status"""
    from app.modules.job_control.models import JobControl

    JobControl.print_jobs()
