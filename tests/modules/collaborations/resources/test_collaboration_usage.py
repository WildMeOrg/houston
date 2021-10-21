# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_use_collaboration(flask_app_client, researcher_1, researcher_2, test_root, db):
    from app.modules.collaborations.models import Collaboration

    transaction_id, test_filename = asset_group_utils.create_bulk_tus_transaction(
        test_root
    )
    asset_group_uuid = None
    collab = None
    try:
        data = asset_group_utils.get_bulk_creation_data(transaction_id, test_filename)

        asset_group_resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = asset_group_resp.json['guid']

        data = {
            'user_guid': str(researcher_1.guid),
        }

        collab_utils.create_collaboration(flask_app_client, researcher_2, data)
        collabs = Collaboration.query.all()
        collab = collabs[0]
        asset_group_utils.read_asset_group(
            flask_app_client, researcher_2, asset_group_uuid, 403
        )
        collab.set_read_approval_state_for_user(researcher_1.guid, 'approved')

        asset_group_utils.read_asset_group(
            flask_app_client, researcher_2, asset_group_uuid
        )

    finally:
        if collab:
            collab.delete()
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)
