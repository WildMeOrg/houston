# -*- coding: utf-8 -*-
"""
Application EDM related tasks for Invoke.
"""

from flask import current_app as app

from tasks.utils import app_context_task


@app_context_task()
def version_check(context):
    """Check for for correct version of EDM"""
    app.edm.version_check()
