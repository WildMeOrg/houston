# -*- coding: utf-8 -*-
"""
Assets resources utils
-------------
"""
import json

from tests import utils as test_utils

PATH = '/api/v1/keywords/'


def patch_keyword(flask_app_client, user, keyword_guid, data, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('keywords:write',)):
        response = flask_app_client.patch(
            '{}{}'.format(PATH, keyword_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'value'})
    else:
        assert response.status_code == expected_status_code
    return response


def create_keyword(
    flask_app_client, user, value, source='user', expected_status_code=200
):
    if user:
        with flask_app_client.login(user, auth_scopes=('keywords:write',)):
            response = flask_app_client.post(
                PATH,
                data=json.dumps({'value': value, 'source': source}),
                content_type='application/json',
            )
    else:
        response = flask_app_client.post(
            PATH,
            data=json.dumps({'value': value}),
            content_type='application/json',
        )
    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response,
            expected_status_code,
            {'guid', 'value'},
        )
    else:
        assert response.status_code == expected_status_code
    return response


def read_keyword(flask_app_client, user, keyword_guid, expected_status_code=200):
    if user:
        with flask_app_client.login(user, auth_scopes=('keywords:read',)):
            response = flask_app_client.get(f'{PATH}{keyword_guid}')
    else:
        response = flask_app_client.get(f'{PATH}{keyword_guid}')

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response,
            200,
            {'guid', 'value'},
        )
    else:
        assert response.status_code == expected_status_code
    return response


def read_all_keywords(flask_app_client, user, expected_status_code=200):
    if user:
        with flask_app_client.login(user, auth_scopes=('keywords:read',)):
            response = flask_app_client.get(PATH)
    else:
        response = flask_app_client.get(PATH)
    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    return response


def delete_keyword(flask_app_client, user, keyword_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('keywords:write',)):
        response = flask_app_client.delete('{}{}'.format(PATH, keyword_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        assert response.status_code == expected_status_code


def merge_keyword(
    flask_app_client,
    user,
    source_keyword_guid,
    target_keyword_guid,
    expected_status_code=200,
):
    merge_path = f'{PATH}{source_keyword_guid}/{target_keyword_guid}/merge'
    if user:
        with flask_app_client.login(user, auth_scopes=('keywords:write',)):
            response = flask_app_client.post(merge_path)
    else:
        response = flask_app_client.post(merge_path)

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response,
            200,
            {'guid', 'value'},
        )
    else:
        assert response.status_code == expected_status_code
    return response
