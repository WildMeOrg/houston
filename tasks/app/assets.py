# -*- coding: utf-8 -*-
"""
Application Asset management related tasks for Invoke.
"""

from ._utils import app_context_task

@app_context_task
def list_all(context):
    """
    Show existing assets.
    """
    from app.modules.assets.models import Asset

    assets = Asset.query.all()

    for asset in assets:
        print("Asset : {} ".format(asset))
