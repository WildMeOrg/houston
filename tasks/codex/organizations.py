# -*- coding: utf-8 -*-
"""
Application Organizations management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing organizations.
    """
    from app.modules.organizations.models import Organization

    organizations = Organization.query.all()
    for organization in organizations:
        print('Organization : {} '.format(organization))
