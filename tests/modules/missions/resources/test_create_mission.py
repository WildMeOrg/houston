# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils
from tests.modules.missions.resources import utils as mission_utils
from tests.utils import random_nonce, random_guid, wait_for_elasticsearch_status
import tests.extensions.tus.utils as tus_utils
import pytest
import tqdm

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_create_and_delete_mission(flask_app_client, data_manager_1):
    # pylint: disable=invalid-name
    from app.modules.missions.models import (
        Mission,
        MissionUserAssignment,
    )

    nonce = random_nonce(8)
    title = 'This is a test mission (%s), please ignore' % (nonce,)
    response = mission_utils.create_mission(
        flask_app_client,
        data_manager_1,
        title,
    )

    mission_guid = response.json['guid']
    read_mission = Mission.query.get(response.json['guid'])
    assert read_mission.title == title
    assert read_mission.owner == data_manager_1

    # Try reading it back
    mission_utils.read_mission(flask_app_client, data_manager_1, mission_guid)

    # And deleting it
    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)

    read_mission = Mission.query.get(mission_guid)
    assert read_mission is None

    read_mission = MissionUserAssignment.query.filter_by(mission_guid=mission_guid).all()
    assert len(read_mission) == 0


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_mission_permission(
    flask_app_client, admin_user, staff_user, regular_user, data_manager_1, data_manager_2
):
    # Before we create any Missions, find out how many are there already
    previous_list = mission_utils.read_all_missions(flask_app_client, staff_user)

    nonce = random_nonce(8)
    response = mission_utils.create_mission(
        flask_app_client,
        data_manager_1,
        'This is a test mission (%s), please ignore' % (nonce,),
    )

    mission_guid = response.json['guid']

    # staff user should be able to read anything
    mission_utils.read_mission(flask_app_client, staff_user, mission_guid)
    mission_utils.read_all_missions(flask_app_client, staff_user)

    # admin user should be able to read any missions as well
    mission_utils.read_mission(flask_app_client, admin_user, mission_guid)
    mission_utils.read_all_missions(flask_app_client, admin_user)

    # user that created mission can read it back plus the list
    mission_utils.read_mission(flask_app_client, data_manager_1, mission_guid)
    list_response = mission_utils.read_all_missions(flask_app_client, data_manager_1)

    # due to the way the tests are run, there may be missions left lying about,
    # don't rely on there only being one
    assert len(list_response.json) == len(previous_list.json) + 1
    mission_present = False
    for mission in list_response.json:
        if mission['guid'] == mission_guid:
            mission_present = True
            break
    assert mission_present

    # a different data manager should also be able to read the mission
    mission_utils.read_mission(flask_app_client, data_manager_2, mission_guid)
    mission_utils.read_all_missions(flask_app_client, data_manager_2)

    # but a regular user should not be able to read the list or the mission
    mission_utils.read_mission(flask_app_client, regular_user, mission_guid, 403)
    mission_utils.read_all_missions(flask_app_client, regular_user, 403)

    # delete it
    mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_delete_mission_cleanup(flask_app_client, data_manager_1, test_root):
    from app.modules.missions.models import (
        Mission,
        MissionCollection,
        MissionTask,
    )

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        nonce = random_nonce(8)
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            'This is a test mission (%s), please ignore' % (nonce,),
        )
        mission_guid = response.json['guid']
        temp_mission = Mission.query.get(mission_guid)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        new_mission_collections = []
        for index in range(3):
            transaction_id = str(random_guid())
            tus_utils.prep_tus_dir(test_root, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce = random_nonce(8)
            description = 'This is a test mission collection (%s), please ignore' % (
                nonce,
            )
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

        previous_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1
        )

        nonce, new_mission_collection1 = new_mission_collections[0]
        nonce, new_mission_collection2 = new_mission_collections[1]
        data = [
            utils.set_union_op('search', {}),
            utils.set_difference_op('collections', [str(new_mission_collection1.guid)]),
            utils.set_difference_op(
                'assets', [str(new_mission_collection2.assets[0].guid)]
            ),
        ]

        # Wait for elasticsearch to catch up
        wait_for_elasticsearch_status(flask_app_client, data_manager_1)

        new_mission_tasks = []
        for index in range(3):
            response = mission_utils.create_mission_task(
                flask_app_client, data_manager_1, mission_guid, data
            )
            mission_task_guid = response.json['guid']
            temp_mission_task = MissionTask.query.get(mission_task_guid)

            new_mission_tasks.append(temp_mission_task)

        current_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1
        )
        assert len(previous_list.json) + len(new_mission_tasks) == len(current_list.json)

        # Check if the mission is showing the correct number of tasks
        assert len(temp_mission.tasks) == len(new_mission_tasks)

        # Check that the API for a mission's tasks agrees
        response = mission_utils.read_mission_tasks_for_mission(
            flask_app_client, data_manager_1, temp_mission.guid
        )
        assert len(response.json) == 3

        missions = Mission.query.all()
        mission_collections = MissionCollection.query.all()
        mission_tasks = MissionTask.query.all()
        assert len(missions) == 1
        assert len(mission_collections) == 3
        assert len(mission_tasks) == 3
    finally:
        missions = Mission.query.all()
        for mission in missions:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission.guid)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)

        missions = Mission.query.all()
        mission_collections = MissionCollection.query.all()
        mission_tasks = MissionTask.query.all()
        assert len(missions) == 0
        assert len(mission_collections) == 0
        assert len(mission_tasks) == 0


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_mission_scalability(flask_app_client, data_manager_1, test_root):
    from app.modules.missions.models import (
        Mission,
        MissionCollection,
        MissionTask,
    )

    ASSETS = 1000
    MISSION_COLLECTIONS = 2
    MISSION_TASKS = 1

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        nonce = random_nonce(8)
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            'This is a test mission (%s), please ignore' % (nonce,),
        )
        mission_guid = response.json['guid']
        temp_mission = Mission.query.get(mission_guid)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        new_mission_collections = []
        for index in tqdm.tqdm(list(range(MISSION_COLLECTIONS))):
            transaction_id = str(random_guid())
            tus_utils.prep_randomized_tus_dir(total=ASSETS, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce = random_nonce(8)
            description = 'This is a test mission collection (%s), please ignore' % (
                nonce,
            )
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

        previous_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1
        )

        nonce, new_mission_collection1 = new_mission_collections[0]
        nonce, new_mission_collection2 = new_mission_collections[1]
        data = [
            utils.set_union_op('search', {}),
        ]

        # Wait for elasticsearch to catch up
        wait_for_elasticsearch_status(flask_app_client, data_manager_1)

        new_mission_tasks = []
        for index in tqdm.tqdm(list(range(MISSION_TASKS))):
            response = mission_utils.create_mission_task(
                flask_app_client, data_manager_1, mission_guid, data
            )
            mission_task_guid = response.json['guid']
            temp_mission_task = MissionTask.query.get(mission_task_guid)

            new_mission_tasks.append(temp_mission_task)

        current_list = mission_utils.read_all_mission_tasks(
            flask_app_client, data_manager_1
        )
        assert len(previous_list.json) + len(new_mission_tasks) == len(current_list.json)

        # Check if the mission is showing the correct number of tasks
        assert len(temp_mission.tasks) == len(new_mission_tasks)

        # Check that the API for a mission's tasks agrees
        response = mission_utils.read_mission_tasks_for_mission(
            flask_app_client, data_manager_1, temp_mission.guid
        )
        assert len(response.json) == MISSION_TASKS

        missions = Mission.query.all()
        mission_collections = MissionCollection.query.all()
        mission_tasks = MissionTask.query.all()
        assert len(missions) == 1
        assert len(mission_collections) == MISSION_COLLECTIONS
        assert len(mission_tasks) == MISSION_TASKS
    finally:
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)

        missions = Mission.query.all()
        mission_collections = MissionCollection.query.all()
        mission_tasks = MissionTask.query.all()
        assert len(missions) == 0
        assert len(mission_collections) == 0
        assert len(mission_tasks) == 0


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_get_mission_assets(flask_app_client, data_manager_1, test_root):
    from app.modules.missions.models import (
        Mission,
        MissionCollection,
    )

    ASSETS = 1000
    MISSION_COLLECTIONS = 2

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        nonce = random_nonce(8)
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            'This is a test mission (%s), please ignore' % (nonce,),
        )
        mission_guid = response.json['guid']
        temp_mission = Mission.query.get(mission_guid)

        previous_list = mission_utils.read_all_mission_collections(
            flask_app_client, data_manager_1
        )

        new_mission_collections = []
        for index in tqdm.tqdm(list(range(MISSION_COLLECTIONS))):
            transaction_id = str(random_guid())
            tus_utils.prep_randomized_tus_dir(total=ASSETS, transaction_id=transaction_id)
            transaction_ids.append(transaction_id)

            nonce = random_nonce(8)
            description = 'This is a test mission collection (%s), please ignore' % (
                nonce,
            )
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

        # Wait for elasticsearch to catch up
        wait_for_elasticsearch_status(flask_app_client, data_manager_1)

        search = {}
        # Check that the API for a mission's collections agrees
        response = mission_utils.elasticsearch_mission_assets(
            flask_app_client, data_manager_1, temp_mission.guid, search
        )
        assets = temp_mission.get_assets()
        assert len(assets) == ASSETS * MISSION_COLLECTIONS
        assert len(response.json) == len(assets)

        search = {
            'range': {
                'size_bytes': {
                    'lte': 10400,
                }
            }
        }

        # Check that the API for a mission's collections agrees
        response = mission_utils.elasticsearch_mission_assets(
            flask_app_client, data_manager_1, temp_mission.guid, search
        )
        assert len(response.json) < 100

        missions = Mission.query.all()
        mission_collections = MissionCollection.query.all()
        assert len(missions) == 1
        assert len(mission_collections) == MISSION_COLLECTIONS
    finally:
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)

        missions = Mission.query.all()
        mission_collections = MissionCollection.query.all()
        assert len(missions) == 0
        assert len(mission_collections) == 0
