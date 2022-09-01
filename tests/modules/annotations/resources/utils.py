# -*- coding: utf-8 -*-
"""
Annotation resources utils
-------------
"""
import json

from tests import utils as test_utils

PATH = '/api/v1/annotations/'

# The creation side of these utils will be specific to scout and codex as the parameters are different but the
# rest of the utils can be shared (apart from the expected keys)
if test_utils.is_module_enabled('codex_annotations'):
    EXPECTED_KEYS = {'guid', 'asset_guid', 'encounter_guid'}
elif test_utils.is_module_enabled('scout_annotations'):
    EXPECTED_KEYS = {'guid', 'asset_guid', 'task_guid'}


def create_annotation_simple(
    flask_app_client,
    user,
    asset_uuid,
    ia_class='test',
    viewpoint='test',
    bounds={'rect': [0, 1, 2, 3]},
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('annotations:write',)):
        response = flask_app_client.post(
            PATH,
            content_type='application/json',
            data=json.dumps(
                {
                    'asset_guid': asset_uuid,
                    'ia_class': ia_class,
                    'viewpoint': viewpoint,
                    'bounds': bounds,
                }
            ),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'asset_guid'})
        assert response.json['asset_guid'] == asset_uuid
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


# NOTE: now (due to DEX-301) an annotation can be made *without* an encounter.  see create_annotation_simple() above.
def create_annotation(
    flask_app_client,
    user,
    asset_uuid,
    encounter_guid,
    ia_class='test',
    viewpoint='test',
    bounds={'rect': [0, 1, 2, 3]},
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('annotations:write',)):
        response = flask_app_client.post(
            PATH,
            content_type='application/json',
            data=json.dumps(
                {
                    'asset_guid': asset_uuid,
                    'encounter_guid': encounter_guid,
                    'ia_class': ia_class,
                    'viewpoint': viewpoint,
                    'bounds': bounds,
                }
            ),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
        assert response.json['asset_guid'] == asset_uuid
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def create_scout_annotation(
    flask_app_client,
    user,
    asset_uuid,
    task_guid,
    ia_class='test',
    viewpoint='test',
    bounds={'rect': [0, 1, 2, 3]},
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('annotations:write',)):
        response = flask_app_client.post(
            PATH,
            content_type='application/json',
            data=json.dumps(
                {
                    'asset_guid': asset_uuid,
                    'task_guid': task_guid,
                    'ia_class': ia_class,
                    'viewpoint': viewpoint,
                    'bounds': bounds,
                }
            ),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
        assert response.json['asset_guid'] == asset_uuid
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_annotation(
    flask_app_client, annotation_guid, user, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('annotations:write',)):
        response = flask_app_client.patch(
            '{}{}'.format(PATH, annotation_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_annotation(
    flask_app_client, user, annotation_guid, expected_status_code=200, expected_keys=None
):
    if expected_keys is None:
        expected_keys = EXPECTED_KEYS
    with flask_app_client.login(user, auth_scopes=('annotations:read',)):
        response = flask_app_client.get('{}{}'.format(PATH, annotation_guid))

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, expected_keys)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_debug(flask_app_client, user, annotation_guid, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('annotations:read',)):
        response = flask_app_client.get(f'{PATH}debug/{annotation_guid}')

    return response


def read_all_annotations(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('annotations:read',)):
        response = flask_app_client.get(PATH)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def delete_annotation(flask_app_client, user, annotation_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('annotations:write',)):
        response = flask_app_client.delete('{}{}'.format(PATH, annotation_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
