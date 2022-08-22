# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.extensions.tus.utils as tus_utils
import tests.modules.missions.resources.utils as mission_utils
from tests.utils import module_unavailable


# Test a bunch of failure scenarios
@pytest.mark.skipif(
    module_unavailable('missions'), reason='MissionCollections module disabled'
)
def test_create_mission_collection(flask_app_client, admin_user, test_root):
    # pylint: disable=invalid-name
    from app.modules.missions.models import Mission, MissionCollection

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    mission_guid, mission_collection_guid = None, None

    try:
        response = mission_utils.create_mission(
            flask_app_client,
            admin_user,
            mission_utils.make_name('mission')[1],
        )
        mission_guid = response.json['guid']
        temp_mission = Mission.query.get(mission_guid)

        description = 'A test mission collection, please ignore'
        response = mission_utils.create_mission_collection_with_tus(
            flask_app_client,
            admin_user,
            description,
            transaction_id,
            temp_mission.guid,
        )
        mission_collection_guid = response.json['guid']
        temp_mission_collection = MissionCollection.query.get(mission_collection_guid)

        assert temp_mission_collection.mission == temp_mission
        assert temp_mission_collection.owner == admin_user
        assert len(temp_mission_collection.assets) == 1
        assert isinstance(temp_mission_collection, MissionCollection)
    finally:
        if mission_collection_guid:
            mission_utils.delete_mission_collection(
                flask_app_client, admin_user, mission_collection_guid
            )
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, admin_user, mission_guid)
        tus_utils.cleanup_tus_dir(transaction_id)
