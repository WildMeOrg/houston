# -*- coding: utf-8 -*-
"""
Application Encounter management related tasks for Invoke.
"""
from flask import current_app

from ._utils import app_context_task

@app_context_task
def list_encounters(context):
    """
    Show existing encounters.
    """
    from app.modules.encounters.models import Encounter

    encounters = Encounter.query.all()

    for encounter in encounters:
        print("Encounter : {} ".format(encounter))
