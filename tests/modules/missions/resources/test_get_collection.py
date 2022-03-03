# -*- coding: utf-8 -*-
import pytest

from tests.utils import (
    module_unavailable,
    random_nonce,
    random_guid,
    wait_for_elasticsearch_status,
)
from tests.modules.missions.resources import utils as mission_utils
import tests.extensions.tus.utils as tus_utils


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_collection_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/missions/collections/wrong-uuid')
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_collection_by_search(flask_app_client, data_manager_1, test_root):
    from app.modules.missions.models import Mission, MissionCollection

    nonce = random_nonce(8)
    response = mission_utils.create_mission(
        flask_app_client,
        data_manager_1,
        'This is a test mission (%s), please ignore' % (nonce,),
    )
    mission_guid = response.json['guid']
    temp_mission = Mission.query.get(mission_guid)
    assert len(temp_mission.collections) == 0

    previous_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1
    )

    transaction_ids = []
    new_mission_collections = []
    for index in range(3):
        transaction_id = str(random_guid())
        tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
        transaction_ids.append(transaction_id)

        nonce = random_nonce(8)
        description = 'This is a test mission collection (%s), please ignore' % (nonce,)
        response = mission_utils.create_mission_collection_with_tus(
            flask_app_client,
            data_manager_1,
            description,
            transaction_id,
            temp_mission.guid,
        )
        mission_collection_guid = response.json['guid']
        temp_mission_collection = MissionCollection.query.get(mission_collection_guid)

        new_mission_collections.append((nonce, temp_mission_collection))

    current_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1
    )
    assert len(previous_list.json) + len(new_mission_collections) == len(
        current_list.json
    )

    # Check if the mission is showing the correct number of collections
    assert len(temp_mission.collections) == len(new_mission_collections)
    assert len(temp_mission.get_assets()) == 3

    # Check that the API for a mission's collections agrees
    response = mission_utils.read_mission_collections_for_mission(
        flask_app_client, data_manager_1, temp_mission.guid
    )
    assert len(response.json) == 3

    # Search mission collections by description segment
    nonce, new_mission_collection = new_mission_collections[0]
    current_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1, search=nonce
    )
    assert len(current_list.json) == 1
    response = current_list.json[0]
    assert response['description'] == new_mission_collection.description

    # Search mission collections by GUID segment
    nonce, new_mission_collection = new_mission_collections[1]
    guid_str = str(new_mission_collection.guid)
    guid_segment = guid_str.split('-')[-1]
    current_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1, search=guid_segment
    )
    assert len(current_list.json) == 1
    response = current_list.json[0]
    assert response['description'] == new_mission_collection.description

    # Search mission collections by owner GUID segment
    nonce, new_mission_collection = new_mission_collections[2]
    assert new_mission_collection.owner == data_manager_1
    guid_str = str(new_mission_collection.owner_guid)
    guid_segment = guid_str.split('-')[-1]
    current_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1, search=guid_segment
    )
    assert len(current_list.json) == len(new_mission_collections)

    # Search mission collections by mission GUID segment
    nonce, new_mission_collection = new_mission_collections[2]
    assert new_mission_collection.mission == temp_mission
    guid_str = str(new_mission_collection.mission_guid)
    guid_segment = guid_str.split('-')[-1]
    current_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1, search=guid_segment
    )
    assert len(current_list.json) == len(new_mission_collections)

    # Limit responses
    limited_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1, search=guid_segment, limit=2
    )
    assert len(current_list.json[:2]) == len(limited_list.json)

    # Limit responses (with offset)
    limited_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1, search=guid_segment, offset=1, limit=2
    )
    assert len(current_list.json[1:3]) == len(limited_list.json)

    # Delete mission collections
    for nonce, new_mission_collection in new_mission_collections:
        mission_utils.delete_mission_collection(
            flask_app_client, data_manager_1, new_mission_collection.guid
        )

    # Delete mission
    mission_utils.delete_mission(flask_app_client, data_manager_1, temp_mission.guid)

    for transaction_id in transaction_ids:
        tus_utils.cleanup_tus_dir(transaction_id)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_assets(flask_app_client, data_manager_1, test_root):
    from app.modules.missions.models import Mission, MissionCollection

    nonce = random_nonce(8)
    response = mission_utils.create_mission(
        flask_app_client,
        data_manager_1,
        'This is a test mission (%s), please ignore' % (nonce,),
    )
    mission_guid = response.json['guid']
    temp_mission = Mission.query.get(mission_guid)
    assert len(temp_mission.collections) == 0

    previous_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1
    )

    transaction_ids = []
    new_mission_collections = []
    for index in range(3):
        transaction_id = str(random_guid())
        tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
        transaction_ids.append(transaction_id)

        nonce = random_nonce(8)
        description = 'This is a test mission collection (%s), please ignore' % (nonce,)
        response = mission_utils.create_mission_collection_with_tus(
            flask_app_client,
            data_manager_1,
            description,
            transaction_id,
            temp_mission.guid,
        )
        mission_collection_guid = response.json['guid']
        temp_mission_collection = MissionCollection.query.get(mission_collection_guid)

        new_mission_collections.append((nonce, temp_mission_collection))

    current_list = mission_utils.read_all_mission_collections(
        flask_app_client, data_manager_1
    )
    assert len(previous_list.json) + len(new_mission_collections) == len(
        current_list.json
    )

    # Check if the mission is showing the correct number of collections
    assert len(temp_mission.collections) == len(new_mission_collections)
    assets = temp_mission.get_assets()
    assert len(assets) == 3

    # Check that the API for a mission's collections agrees
    response = mission_utils.read_mission_collections_for_mission(
        flask_app_client, data_manager_1, temp_mission.guid
    )
    assert len(response.json) == 3

    # Wait for elasticsearch to catch up
    wait_for_elasticsearch_status(flask_app_client, data_manager_1)

    search = {
        'from': 0,
        'size': 10,
        'query': {
            'bool': {
                'filter': [],
                'must_not': [],
            }
        },
    }

    # Check that the API for a mission's collections agrees
    response = mission_utils.elasticsearch_mission_assets(
        flask_app_client, data_manager_1, temp_mission.guid, search
    )
    assert len(response.json) == len(assets)

    # Delete mission
    mission_utils.delete_mission(flask_app_client, data_manager_1, temp_mission.guid)

    for transaction_id in transaction_ids:
        tus_utils.cleanup_tus_dir(transaction_id)
