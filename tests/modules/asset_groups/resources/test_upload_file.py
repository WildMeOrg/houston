# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from os.path import basename

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_open_submission(flask_app_client, regular_user, test_root, db):
    # pylint: disable=invalid-name
    temp_submission = None
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)

    try:
        from app.modules.asset_groups.models import AssetGroup

        data = asset_group_utils.AssetGroupCreationData(transaction_id)
        data.add_filename(0, test_filename)
        response = asset_group_utils.create_asset_group(
            flask_app_client, regular_user, data.get()
        )

        temp_submission = AssetGroup.query.get(response.json['guid'])

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {
            'guid',
            'commit',
            'major_type',
            'owner_guid',
        }
        # TODO this is what the test checked, that there was not commit, what we are now specifically not permitting
        # assert temp_submission.commit is None
    finally:
        # Restore original state
        if temp_submission is not None:
            temp_submission.delete()


def _upload_content(path):
    bname = basename(path)
    return open(path, 'rb'), bname
