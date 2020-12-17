# -*- coding: utf-8 -*-
"""
Application Organizations management related tasks for Invoke.
"""

from ._utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing organizations.
    """
    from app.modules.organizations.models import Organization

    organizations = Organization.query.all()
    for organization in organizations:
        print('Organization : {} '.format(organization))


@app_context_task
def sync_edm(context, refresh=False):
    """
    Sync the organizations from the EDM onto the local Hudson
    """
    from app.modules.organizations.models import Organization

    Organization.edm_sync_all(refresh=refresh)
