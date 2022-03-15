# -*- coding: utf-8 -*-
"""
Application AssetGroup management related tasks for Invoke.
"""

from tasks.utils import app_context_task
from app.extensions import db
from app.modules.integrity.models import Integrity


@app_context_task()
def create_new(context):
    """
    Create new integity check.
    """
    integ = Integrity()
    with db.session.begin():
        db.session.add(integ)


@app_context_task()
def all(context):
    """
    Show existing integity results.
    """

    integ_checks = Integrity.query.all()
    for check in integ_checks:
        print(
            f'Integrity check : GUID:{check.guid} created: {check.created} result: {check.result}'
        )
