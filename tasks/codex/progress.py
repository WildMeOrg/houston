# -*- coding: utf-8 -*-
"""
Application Progress management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing progress.
    """
    from app.modules.progress.models import Progress

    progress = Progress.query.all()
    for progress in progress:
        print('Progress : {} '.format(progress))
