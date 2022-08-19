# -*- coding: utf-8 -*-
from tests.modules.site_settings.resources import utils


def test_relationship_type_roles(flask_app_client, admin_user):
    relationship_type_roles = {
        '49e85f81-c11a-42be-9097-d22c61345ed8': {
            'guid': '49e85f81-c11a-42be-9097-d22c61345ed8',
            'label': 'familial',
            'roles': [
                {
                    'guid': '1b62eb1a-0b80-4c2d-b914-923beba8863c',
                    'label': 'mother',
                },
                {'guid': 'ea5dbbb3-cc47-4d44-b460-2518a25dcb13', 'label': 'father'},
                {'guid': '4e38325a-46de-47e8-bb02-8ef0dbf54860', 'label': 'son'},
                {'guid': '8299f080-22ed-40da-8c06-af57ada64644', 'label': 'daughter'},
            ],
        },
    }
    # Update relationship_type_roles
    utils.modify_main_settings(
        flask_app_client,
        admin_user,
        relationship_type_roles,
        conf_key='relationship_type_roles',
    )
    # Get all settings
    response = utils.read_main_settings(flask_app_client, admin_user)
    assert response.json['relationship_type_roles']['value'] == relationship_type_roles

    # Check relationship_type_roles validation
    error = "Houston Setting key=relationship_type_roles, value incorrect type value=['rod', 'jane', 'freddy'],needs to be <class 'dict'>"
    utils.modify_main_settings(
        flask_app_client,
        admin_user,
        ['rod', 'jane', 'freddy'],
        conf_key='relationship_type_roles',
        expected_status_code=400,
        expected_error=error,
    )

    utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {
            '49e85f81-c11a-42be-9097-d22c61345ed8': {
                'guid': '49e85f81-c11a-42be-9097-d22c61345ed8',
                'label': 'Family',
                'roles': [
                    {'label': 'Mother'},
                ],
            },
        },
        conf_key='relationship_type_roles',
        expected_status_code=400,
        expected_error='"roles.0.guid": Missing data for required field.',
    )

    utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {
            '49e85f81-c11a-42be-9097-d22c61345ed8': {
                'guid': '49e85f81-c11a-42be-9097-d22c61345ed8',
                'label': 'Family',
                'roles': [
                    {
                        'guid': '1b62eb1a',
                        'label': 'Mother',
                    },
                ],
            },
        },
        conf_key='relationship_type_roles',
        expected_status_code=400,
        expected_error='"roles.0.guid": Not a valid UUID.',
    )
