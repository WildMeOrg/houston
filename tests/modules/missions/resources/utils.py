# -*- coding: utf-8 -*-
"""
Mission resources utils
-------------
"""
import json
from unittest import mock

from tests import utils as test_utils


PATH_MISSIONS = '/api/v1/missions/'
PATH_MISSION_COLLECTIONS = '/api/v1/missions/collections/'
PATH_MISSION_COLLECTIONS_FOR_MISSION = '/api/v1/missions/%s/collections/'
PATH_MISSION_TASKS = '/api/v1/missions/tasks/'
PATH_MISSION_TASKS_FOR_MISSION = '/api/v1/missions/%s/tasks/'


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


def create_mission_collection_with_tus(
    flask_app_client,
    user,
    description,
    transaction_id,
    mission_guid,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('missions:write',)):
        response = flask_app_client.post(
            f'{PATH_MISSIONS}{mission_guid}/tus/collect/',
            content_type='application/json',
            data=json.dumps(
                {'description': description, 'transaction_id': transaction_id}
            ),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'description'})
        assert response.json['description'] == description
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


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


def read_all_mission_collections(
    flask_app_client, user, expected_status_code=200, **kwargs
):
    assert set(kwargs.keys()) <= {'search', 'limit', 'offset'}

    with flask_app_client.login(user, auth_scopes=('missions:read',)):
        response = flask_app_client.get(
            PATH_MISSION_COLLECTIONS,
            query_string=kwargs,
        )

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_mission_collections_for_mission(
    flask_app_client, user, mission_guid, expected_status_code=200
):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='missions:read',
        path=PATH_MISSION_COLLECTIONS_FOR_MISSION % (mission_guid,),
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


def create_mission_task(
    flask_app_client, user, mission_guid, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('missions:write',)):
        response = flask_app_client.post(
            PATH_MISSION_TASKS_FOR_MISSION % (mission_guid,),
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


def update_mission_task(
    flask_app_client, user, mission_task_guid, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('missions:write',)):
        response = flask_app_client.post(
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


def read_all_mission_tasks(flask_app_client, user, expected_status_code=200, **kwargs):
    assert set(kwargs.keys()) <= {'search', 'limit', 'offset'}

    with flask_app_client.login(user, auth_scopes=('missions:read',)):
        response = flask_app_client.get(
            PATH_MISSION_TASKS,
            query_string=kwargs,
        )

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_mission_tasks_for_mission(
    flask_app_client, user, mission_guid, expected_status_code=200
):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='missions:read',
        path=PATH_MISSION_TASKS_FOR_MISSION % (mission_guid,),
        expected_status_code=expected_status_code,
    )


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
