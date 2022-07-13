# -*- coding: utf-8 -*-
"""
Configuration resources utils
-------------
"""
import uuid

from tests import utils as test_utils

EXPECTED_KEYS = {'response'}
SETTING_PATH = '/api/v1/site-settings'


def _read_settings(
    flask_app_client,
    user,
    conf_path,
    expected_status_code=None,
):
    res = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='site-settings:read',
        path=conf_path,
        expected_status_code=expected_status_code,
        response_200=EXPECTED_KEYS,
        response_error={'message'},
    )
    return res


def read_main_settings(
    flask_app_client,
    user,
    conf_path='block',
    expected_status_code=200,
):

    path = f'{SETTING_PATH}/main/{conf_path}'

    return _read_settings(flask_app_client, user, path, expected_status_code)


def read_main_settings_definition(
    flask_app_client,
    user,
    conf_path='block',
    expected_status_code=200,
):
    path = f'{SETTING_PATH}/definition/main/{conf_path}'
    return _read_settings(flask_app_client, user, path, expected_status_code)


def read_file(flask_app_client, user, filename, expected_status_code=302):
    path = f'{SETTING_PATH}/file/{filename}'

    # Files are special in that they have no json response so cannot be validated by the normal utils
    resp = _read_settings(flask_app_client, user, path)
    assert resp.status_code == expected_status_code

    return resp


def _modify_setting(
    flask_app_client,
    user,
    data,
    conf_path,
    expected_status_code=None,
    expected_error=None,
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='site-settings:write',
        path=conf_path,
        data=data,
        expected_status_code=expected_status_code,
        response_200=None,
        expected_error=expected_error,
    )


def modify_main_settings(
    flask_app_client,
    user,
    data,
    conf_key='block',
    expected_status_code=200,
    expected_error=None,
):
    if conf_key == 'block':
        path = f'{SETTING_PATH}/main'
    else:
        path = f'{SETTING_PATH}/main/{conf_key}'
    return _modify_setting(
        flask_app_client, user, data, path, expected_status_code, expected_error
    )


def write_file(flask_app_client, user, data, expected_status_code=200):
    path = f'{SETTING_PATH}/file'
    return _modify_setting(
        flask_app_client, user, data, path, expected_status_code, {'file_upload_guid'}
    )


def custom_field_create(
    flask_app_client,
    user,
    name,
    cls='Occurrence',
    type='string',
    multiple=False,
):
    data = {
        'definitions': [
            {
                'name': name,
                'type': type,
                'multiple': multiple,
            }
        ]
    }
    payload = {}
    payload['site.custom.customFields.' + cls] = data
    response = modify_main_settings(flask_app_client, user, payload)
    cfd_list = response.json.get('updatedCustomFieldDefinitionIds', None)
    assert cfd_list
    return cfd_list[0]


def patch_main_setting(
    flask_app_client,
    user,
    conf_key,
    data,
    expected_status_code=200,
):
    if conf_key == 'block':
        path = f'{SETTING_PATH}/main'
    else:
        path = f'{SETTING_PATH}/main/{conf_key}'

    return test_utils.patch_via_flask(
        flask_app_client,
        user,
        scopes='site-settings:write',
        path=path,
        data=data,
        expected_status_code=expected_status_code,
        response_200=EXPECTED_KEYS,
    )


def _delete_setting(
    flask_app_client,
    user,
    conf_path,
    expected_status_code=200,
):
    res = test_utils.delete_via_flask(
        flask_app_client,
        user,
        scopes='site-settings:write',
        path=conf_path,
        expected_status_code=expected_status_code,
    )

    return res


def delete_main_setting(
    flask_app_client,
    user,
    conf_key,
    expected_status_code=204,
):
    if conf_key == 'block':
        path = f'{SETTING_PATH}/main'
    else:
        path = f'{SETTING_PATH}/main/{conf_key}'
    return _delete_setting(flask_app_client, user, path, expected_status_code)


def delete_file(
    flask_app_client,
    user,
    conf_key,
    expected_status_code=204,
):
    path = f'{SETTING_PATH}/file/{conf_key}'
    _delete_setting(flask_app_client, user, path, expected_status_code)


def extract_from_main_block(main_block, field):
    # navigate through the fluff to find the data but don't assume that anything is there
    if 'response' in main_block and 'configuration' in main_block['response']:
        config = main_block['response']['configuration']
        if field in config and 'value' in config[field]:
            return config[field]['value']
    return None


# will create one if we dont have any (yet)
def get_some_taxonomy_dict(flask_app_client, admin_user):
    block_data = read_main_settings(flask_app_client, admin_user).json
    species = extract_from_main_block(block_data, 'site.species')

    if species and isinstance(species, list) and len(species) > 0:
        return species[0]

    # need to make one
    vals = [
        {'commonNames': ['Example'], 'scientificName': 'Exempli gratia', 'itisTsn': -1234}
    ]
    modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': vals},
        'site.species',
    )
    response = read_main_settings(flask_app_client, admin_user).json
    species = extract_from_main_block(response, 'site.species')
    assert species
    assert isinstance(species, list)
    assert len(species) > 0
    return species[0]


# Helper util to get (and create if necessary) the regions we will use for testing
def get_and_ensure_test_regions(flask_app_client, admin_user):
    block_data = read_main_settings(flask_app_client, admin_user).json
    current_regions = extract_from_main_block(block_data, 'site.custom.regions')

    names = []
    regions = []
    if 'locationID' in current_regions:
        regions = current_regions['locationID']
        names = [region['name'] for region in regions]

    updated = False
    if 'Wiltshire' not in names:
        regions.append({'id': str(uuid.uuid4()), 'name': 'Wiltshire'})
        updated = True
    if 'Mongolia' not in names:
        regions.append({'id': str(uuid.uuid4()), 'name': 'Mongolia'})
        updated = True
    if 'France' not in names:
        regions.append({'id': str(uuid.uuid4()), 'name': 'France'})
        updated = True
    if updated:
        modify_main_settings(
            flask_app_client,
            admin_user,
            {'_value': {'locationID': regions}},
            'site.custom.regions',
        )

    return regions
