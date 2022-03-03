# -*- coding: utf-8 -*-
"""
Application Asset management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing assets.
    """
    from app.modules.assets.models import Asset

    assets = Asset.query.all()

    for asset in assets:
        print('Asset : {} '.format(asset))


@app_context_task
def get_stored_filename(context, input_filename):
    from app.utils import get_stored_filename

    print(get_stored_filename(input_filename))
