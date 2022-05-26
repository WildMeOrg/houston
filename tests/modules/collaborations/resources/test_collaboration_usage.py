# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.collaborations.resources.utils as collab_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_use_collaboration(
    flask_app_client, researcher_1, researcher_2, test_root, db, request
):
    from app.modules.collaborations.models import Collaboration

    (
        asset_group_uuid,
        asset_group_sighting_guid,
        asset_uuid,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )

    data = {
        'user_guid': str(researcher_1.guid),
    }

    collab_utils.create_collaboration(flask_app_client, researcher_2, data)
    collabs = Collaboration.query.all()
    collab = collabs[0]
    request.addfinalizer(lambda: collab.delete())

    asset_group_utils.read_asset_group(
        flask_app_client, researcher_2, asset_group_uuid, 403
    )
    collab.set_read_approval_state_for_user(researcher_1.guid, 'approved')

    asset_group_utils.read_asset_group(flask_app_client, researcher_2, asset_group_uuid)
