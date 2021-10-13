# -*- coding: utf-8 -*-
"""
Application projects management related tasks for Invoke.
"""

from ._utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing projects.
    """
    from app.modules.projects.models import Project

    projects = Project.query.all()
    for project in projects:
        print('Project : {} '.format(project))
