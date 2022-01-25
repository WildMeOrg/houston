# -*- coding: utf-8 -*-
"""
Mission resources utils
-------------
"""
import json
import os
import shutil
from unittest import mock

from config import get_preliminary_config

from tests import utils as test_utils
from tests import TEST_MISSION_COLLECTION_UUID, TEST_EMPTY_MISSION_COLLECTION_UUID


PATH_MISSIONS = '/api/v1/missions/'
PATH_MISSION_COLLECTIONS = '/api/v1/missions/collections/'
PATH_MISSION_TASKS = '/api/v1/missions/tasks/'


EXPECTED_MISSION_COLLECTION_SIGHTING_FIELDS = {
    'guid',
    'stage',
    'decimalLatitude',
    'decimalLongitude',
    'encounters',
    'locationId',
    'time',
    'timeSpecificity',
    'completion',
    'assets',
}

ANNOTATION_UUIDS = [
    '1891ca05-5fa5-4e52-bb30-8ee80941c2fc',
    '0c6f3a16-c3f0-4f8d-a47d-951e49b0dacb',
]

###################################################################################################################
# Simple helpers for use with most tests
###################################################################################################################


def create_mission(flask_app_client, user, title, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('missions:write',)):
        response = flask_app_client.post(
            PATH_MISSIONS,
            content_type='application/json',
            data=json.dumps({'title': title}),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
        assert response.json['title'] == title
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_mission(flask_app_client, mission_guid, user, data, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('missions:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH_MISSIONS, mission_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_mission(flask_app_client, user, mission_guid, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('missions:read',)):
        response = flask_app_client.get('%s%s' % (PATH_MISSIONS, mission_guid))

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_missions(flask_app_client, user, expected_status_code=200, **kwargs):
    assert set(kwargs.keys()) <= {'search', 'limit', 'offset'}

    with flask_app_client.login(user, auth_scopes=('missions:read',)):
        response = flask_app_client.get(
            PATH_MISSIONS,
            query_string=kwargs,
        )

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def delete_mission(flask_app_client, user, mission_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('missions:delete',)):
        response = flask_app_client.delete('%s%s' % (PATH_MISSIONS, mission_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


def patch_mission_collection(
    flask_app_client, user, mission_collection_guid, data, expected_status_code=200
):
    return test_utils.patch_via_flask(
        flask_app_client,
        user,
        scopes='missions:write',
        path=f'{PATH_MISSION_COLLECTIONS}{mission_collection_guid}',
        data=data,
        expected_status_code=expected_status_code,
        response_200={'guid', 'description', 'major_type'},
    )


def read_mission_collection(
    flask_app_client, user, mission_collection_guid, expected_status_code=200
):

    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='missions:read',
        path=f'{PATH_MISSION_COLLECTIONS}{mission_collection_guid}',
        expected_status_code=expected_status_code,
        response_200={'guid', 'description', 'major_type'},
    )


def read_all_mission_collections(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='missions:read',
        path=PATH_MISSION_COLLECTIONS,
        expected_status_code=expected_status_code,
    )


def delete_mission_collection(
    flask_app_client, user, mission_collection_guid, expected_status_code=204
):
    from app.modules.missions.models import MissionCollection
    from app.modules.missions.tasks import delete_remote

    with mock.patch('app.modules.missions.tasks') as tasks:
        # Do delete_remote in the foreground immediately instead of using a
        # celery worker in the background
        tasks.delete_remote.delay.side_effect = lambda *args, **kwargs: delete_remote(
            *args, **kwargs
        )
        with flask_app_client.login(user, auth_scopes=('missions:write',)):
            response = flask_app_client.delete(
                '%s%s' % (PATH_MISSION_COLLECTIONS, mission_collection_guid)
            )

    if expected_status_code == 204:
        assert response.status_code == 204
        assert not MissionCollection.is_on_remote(mission_collection_guid)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


def validate_file_data(test_root, data, filename):
    import hashlib

    from PIL import Image
    import io
    from app.modules.assets.models import Asset

    full_path = f'{test_root}/{filename}'
    full_path = full_path.replace('/code/', '')

    with Image.open(full_path) as source_image:
        source_image.thumbnail(Asset.FORMATS['master'])
        rgb = source_image.convert('RGB')
        # hashlib.md5(source_image.tobytes()).hexdigest()
        # should have worked but didn't
        with io.BytesIO() as mem_file:
            rgb.save(mem_file, 'JPEG')
            md5sum = hashlib.md5(mem_file.getvalue()).hexdigest()

    assert hashlib.md5(data).hexdigest() == md5sum


# multiple tests clone a mission_collection, do something with it and clean it up. Make sure this always happens using a
# class with a cleanup method to be called if any assertions fail
class CloneMissionCollection(object):
    def __init__(self, client, owner, guid, force_clone):
        from app.modules.missions.models import MissionCollection

        self.mission_collection = None
        self.guid = guid

        # Allow the option of forced cloning, this could raise an exception if the assertion fails
        # but this does not need to be in any try/except/finally construct as no resources are allocated yet
        if force_clone:
            database_path = get_preliminary_config().MISSION_COLLECTION_DATABASE_PATH
            mission_collection_path = os.path.join(database_path, str(guid))

            if os.path.exists(mission_collection_path):
                shutil.rmtree(mission_collection_path)
            assert not os.path.exists(mission_collection_path)

        url = f'{PATH_MISSION_COLLECTIONS}{guid}'
        with client.login(owner, auth_scopes=('missions:read',)):
            self.response = client.get(url)

        # only store the mission_collection if the clone worked
        if self.response.status_code == 200:
            self.mission_collection = MissionCollection.query.get(
                self.response.json['guid']
            )

        elif self.response.status_code in (428, 403):
            # 428 Precondition Required
            # 403 Forbidden
            with client.login(owner, auth_scopes=('missions:write',)):
                self.response = client.post(url)

            # only store the mission_collection if the clone worked
            if self.response.status_code == 200:
                self.mission_collection = MissionCollection.query.get(
                    self.response.json['guid']
                )

        else:
            assert (
                False
            ), f'url={url} status_code={self.response.status_code} data={self.response.data}'

    def remove_files(self):
        database_path = get_preliminary_config().MISSION_COLLECTION_DATABASE_PATH
        mission_collection_path = os.path.join(database_path, str(self.guid))
        if os.path.exists(mission_collection_path):
            shutil.rmtree(mission_collection_path)

    def cleanup(self):
        # Restore original state if not one of the mission collection fixtures
        if str(self.guid) not in (
            TEST_MISSION_COLLECTION_UUID,
            TEST_EMPTY_MISSION_COLLECTION_UUID,
        ):
            if self.mission_collection is not None:
                self.mission_collection.delete()
                self.mission_collection = None
            self.remove_files()


# Clone the mission_collection
def clone_mission_collection(
    client,
    owner,
    guid,
    force_clone=False,
    expect_failure=False,
):
    clone = CloneMissionCollection(client, owner, guid, force_clone)

    if not expect_failure:
        assert clone.response.status_code == 200, clone.response.data
    return clone


def create_mission_task(flask_app_client, user, title, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('missions:write',)):
        response = flask_app_client.post(
            PATH_MISSION_TASKS,
            content_type='application/json',
            data=json.dumps({'title': title}),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
        assert response.json['title'] == title
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_mission_task(
    flask_app_client, mission_task_guid, user, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('missions:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH_MISSION_TASKS, mission_task_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_mission_task(
    flask_app_client, user, mission_task_guid, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('missions:read',)):
        response = flask_app_client.get('%s%s' % (PATH_MISSION_TASKS, mission_task_guid))

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'title'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_mission_tasks(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('missions:read',)):
        response = flask_app_client.get(PATH_MISSION_TASKS)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def delete_mission_task(
    flask_app_client, user, mission_task_guid, expected_status_code=204
):
    with flask_app_client.login(user, auth_scopes=('missions:delete',)):
        response = flask_app_client.delete(
            '%s%s' % (PATH_MISSION_TASKS, mission_task_guid)
        )

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
