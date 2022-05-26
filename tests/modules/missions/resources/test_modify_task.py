# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import datetime
import time

import pytest

import tests.extensions.tus.utils as tus_utils
from tests import utils
from tests.modules.missions.resources import utils as mission_utils
from tests.utils import module_unavailable, random_guid, wait_for_elasticsearch_status


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_modify_mission_task_users(
    db, flask_app_client, data_manager_1, data_manager_2, test_root
):
    # pylint: disable=invalid-name
    from app.extensions import elasticsearch as es
    from app.modules.assets.models import Asset
    from app.modules.missions.models import Mission, MissionCollection, MissionTask

    if es.is_disabled():
        return

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            mission_utils.make_name('mission')[1],
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

            nonce, description = mission_utils.make_name('mission collection')
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

        nonce, new_mission_collection1 = new_mission_collections[0]
        nonce, new_mission_collection2 = new_mission_collections[1]
        data = [
            utils.set_union_op('search', {}),
            utils.set_difference_op('collections', [str(new_mission_collection1.guid)]),
            utils.set_difference_op(
                'assets', [str(new_mission_collection2.assets[0].guid)]
            ),
        ]

        now = datetime.datetime.utcnow()

        with es.session.begin(blocking=True):
            Asset.index_all(force=True)

        trial = 0
        while True:
            trial += 1

            if trial > 10:
                raise RuntimeError

            # Wait for elasticsearch to catch up
            wait_for_elasticsearch_status(flask_app_client, data_manager_1)

            try:
                assets = Asset.query.all()
                for asset in assets:
                    assert asset.elasticsearchable
                    assert asset.indexed > now

                response = mission_utils.create_mission_task(
                    flask_app_client, data_manager_1, mission_guid, data
                )
                mission_task_guid = response.json['guid']
                assert len(response.json['assets']) == 1

                break
            except AssertionError:
                continue

            time.sleep(1)

        mission_task = MissionTask.query.get(mission_task_guid)
        assert len(mission_task.get_members()) == 1

        data = [
            utils.patch_test_op(data_manager_1.password_secret),
            utils.patch_add_op('user', '%s' % data_manager_2.guid),
        ]
        mission_utils.patch_mission_task(
            flask_app_client, mission_task_guid, data_manager_1, data
        )
        assert len(mission_task.get_members()) == 2

        data = [
            utils.patch_test_op(data_manager_1.password_secret),
            utils.patch_remove_op('user', '%s' % data_manager_2.guid),
        ]
        mission_utils.patch_mission_task(
            flask_app_client, mission_task_guid, data_manager_1, data
        )
        assert len(mission_task.get_members()) == 1

        data = [
            utils.set_union_op('assets', [str(new_mission_collection2.assets[0].guid)]),
        ]
        response = mission_utils.update_mission_task(
            flask_app_client, data_manager_1, mission_task_guid, data
        )
        assert len(response.json['assets']) == 2

        mission_utils.delete_mission_task(
            flask_app_client, data_manager_1, mission_task_guid
        )
    finally:
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)


@pytest.mark.skipif(module_unavailable('missions'), reason='Missions module disabled')
def test_owner_permission(flask_app_client, data_manager_1, data_manager_2, test_root):
    from app.modules.missions.models import Mission, MissionCollection

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    transaction_ids = []
    transaction_ids.append(transaction_id)
    mission_guid = None

    try:
        response = mission_utils.create_mission(
            flask_app_client,
            data_manager_1,
            mission_utils.make_name('mission')[1],
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

            nonce, description = mission_utils.make_name('mission collection')
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

        response = mission_utils.create_mission_task(
            flask_app_client, data_manager_1, mission_guid, data
        )
        mission_task_guid = response.json['guid']

        # another user cannot update the title
        data = [
            utils.patch_test_op(data_manager_2.password_secret),
            utils.patch_add_op('title', 'Invalid update'),
        ]
        mission_utils.patch_mission_task(
            flask_app_client, mission_task_guid, data_manager_2, data, 409
        )

        # Owner can do that
        data = [
            utils.patch_test_op(data_manager_1.password_secret),
            utils.patch_add_op('title', 'An owner modified test task, please ignore'),
        ]
        response = mission_utils.patch_mission_task(
            flask_app_client, mission_task_guid, data_manager_1, data
        )
        assert response.json['title'] == 'An owner modified test task, please ignore'

        # add data manager 2 user to the task
        data = [
            utils.patch_test_op(data_manager_1.password_secret),
            utils.patch_add_op('user', '%s' % data_manager_2.guid),
        ]
        mission_utils.patch_mission_task(
            flask_app_client, mission_task_guid, data_manager_1, data
        )

        # make them the owner
        data = [
            utils.patch_test_op(data_manager_1.password_secret),
            utils.patch_add_op('owner', '%s' % data_manager_2.guid),
        ]
        mission_utils.patch_mission_task(
            flask_app_client, mission_task_guid, data_manager_1, data
        )

        # try to remove a user as data manager 1, no longer owner, should fail
        data = [
            utils.patch_test_op(data_manager_1.password_secret),
            utils.patch_remove_op('user', '%s' % data_manager_2.guid),
        ]
        mission_utils.patch_mission_task(
            flask_app_client, mission_task_guid, data_manager_1, data, 409
        )

        mission_utils.delete_mission_task(
            flask_app_client, data_manager_1, mission_task_guid
        )
    finally:
        if mission_guid:
            mission_utils.delete_mission(flask_app_client, data_manager_1, mission_guid)
        for transaction_id in transaction_ids:
            tus_utils.cleanup_tus_dir(transaction_id)
