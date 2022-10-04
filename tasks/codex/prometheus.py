# -*- coding: utf-8 -*-
"""
Application projects management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task
def update(context, debug=False):
    """
    Manually update prometheus, very useful for debugging
    """
    from app.extensions.prometheus import update

    if debug:
        breakpoint()
    update()
