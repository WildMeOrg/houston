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
        print('Asset : {} '.format(asset))


@app_context_task(
    help={
        'guid': 'guid of asset to sync',
    }
)
def sync_from_acm(context, guid):
    """
    Sync a single asset from ACM
    """
    from app.modules.assets.models import AssetSync

    AssetSync.acm_sync_item(guid)
