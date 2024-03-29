# -*- coding: utf-8 -*-
"""
Application Encounter management related tasks for Invoke.
"""
from tasks.utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing encounters.
    """
    from app.modules.encounters.models import Encounter

    encounters = Encounter.query.all()

    for encounter in encounters:
        print('Encounter : {} '.format(encounter))
