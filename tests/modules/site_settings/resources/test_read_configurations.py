# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from tests.modules.site_settings.resources import utils as conf_utils
from tests.utils import extension_unavailable, module_unavailable


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_read_site_settings(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    test_key = 'site.name'
    response = conf_utils.read_main_settings(flask_app_client, researcher_1, test_key)
    assert response.json['response']['id'] == test_key
    response = conf_utils.read_main_settings_definition(
        flask_app_client, researcher_1, test_key
    )
    assert response.json['response']['configurationId'] == test_key
    assert response.json['response']['fieldType'] == 'string'

    # a bad key
    response = conf_utils.read_main_settings(
        flask_app_client, researcher_1, '__INVALID_KEY__', expected_status_code=400
    )

    from app.modules.ia_config_reader import IaConfig

    ia_config_reader = IaConfig()
    species = ia_config_reader.get_configured_species()
    config_def_response = conf_utils.read_main_settings_definition(
        flask_app_client, researcher_1, 'site.species'
    )
    # note: this relies on IaConfig and get_configured_species() not changing too radically
    assert len(config_def_response.json['response']['suggestedValues']) >= len(species)
    for i in range(len(species)):
        assert (
            config_def_response.json['response']['suggestedValues'][i]['scientificName']
            == species[len(species) - i - 1]
        )

    config_def_response = conf_utils.read_main_settings_definition(
        flask_app_client, researcher_1
    )
    assert len(
        config_def_response.json['response']['configuration']['site.species'][
            'suggestedValues'
        ]
    ) >= len(species)
    for i in range(len(species)):
        assert (
            config_def_response.json['response']['configuration']['site.species'][
                'suggestedValues'
            ][i]['scientificName']
            == species[len(species) - i - 1]
        )

    # test private (will give 403 to non-admin)
    response = conf_utils.read_main_settings(
        flask_app_client, researcher_1, 'site.testSecret', expected_status_code=403
    )


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_alter_settings(flask_app_client, admin_user):
    response = conf_utils.read_main_settings(flask_app_client, admin_user, 'site.species')
    assert 'value' in response.json['response']
    vals = response.json['response']['value']
    vals.append({'commonNames': ['Test data'], 'scientificName': 'Testus datum'})
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': vals},
        'site.species',
    )
    response = conf_utils.read_main_settings(flask_app_client, admin_user, 'site.species')
    assert 'value' in response.json['response']
    assert response.json['response']['value'][-1]['scientificName'] == 'Testus datum'
    # restore original list
    vals.pop()
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': vals},
        'site.species',
    )


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_alter_custom_fields(flask_app_client, admin_user):

    categories = conf_utils.read_main_settings(
        flask_app_client, admin_user, 'site.custom.customFieldCategories'
    )
    assert 'value' in categories.json['response']
    cats = categories.json['response']['value']
    cats.append(
        {
            'label': 'sighting_category 1',
            'id': '252ef07f-252d-495c-ab97-4e9a15cd9aa7',
            'type': 'sighting',
            'timeCreated': 1649764520424,
            'required': 'false',
        }
    )
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': cats},
        'site.custom.customFieldCategories',
    )

    occ_cf_rsp = conf_utils.read_main_settings(
        flask_app_client, admin_user, 'site.custom.customFields.Occurrence'
    )

    assert 'value' in occ_cf_rsp.json['response']
    occ_cfs = occ_cf_rsp.json['response']['value']
    if occ_cfs == []:
        occ_cfs = {}
    if 'definitions' not in occ_cfs:
        occ_cfs['definitions'] = []

    occ_cfs['definitions'].append(
        {
            'className': 'org.ecocean.Occurrence',
            'default': 'woo',
            'id': str(uuid.uuid4()),
            'multiple': False,
            'name': 'field_name',
            'required': False,
            'schema': {
                'category': '252ef07f-252d-495c-ab97-4e9a15cd9aa7',
                'description': 'wibble de woo',
                'displayType': 'string',
                'label': 'Wibble',
            },
            'timeCreated': 1649765490770,
            'type': 'string',
        }
    )
    occ_cfs['definitions'].append(
        {
            'className': 'org.ecocean.Occurrence',
            'default': 'wobble',
            'id': str(uuid.uuid4()),
            'multiple': False,
            'name': 'field_name',
            'required': False,
            'schema': {
                'category': '252ef07f-252d-495c-ab97-4e9a15cd9aa7',
                'description': "They don't fall down",
                'displayType': 'string',
                'label': 'Weeble',
            },
            'timeCreated': 1649765490770,
            'type': 'string',
        }
    )

    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': occ_cfs},
        'site.custom.customFields.Sighting',
    )
    occ_cf_rsp = conf_utils.read_main_settings(
        flask_app_client, admin_user, 'site.custom.customFields.Occurrence'
    )

    defaults = [
        definit['default']
        for definit in occ_cf_rsp.json['response']['value']['definitions']
        if 'default' in definit
    ]
    assert 'woo' in defaults
    assert 'wobble' in defaults

    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': cats},
        'site.custom.customFieldCategories',
    )

    first = occ_cf_rsp.json['response']['value']['definitions'].pop(0)
    second = occ_cf_rsp.json['response']['value']['definitions'].pop(0)

    conf_utils.delete_main_setting(
        flask_app_client, admin_user, f'site.custom.customFields.Sighting/{first["id"]}'
    )
    # Try via the patch API too
    conf_utils.delete_main_setting(
        flask_app_client,
        admin_user,
        f'site.custom.customFields.Occurrence/{second["id"]}',
    )
    patch_data = [
        {
            'op': 'remove',
            'path': f'/site.custom.customFields.Occurrence/{first["id"]}',
        },
    ]
    conf_utils.patch_main_setting(
        flask_app_client,
        admin_user,
        'block',
        patch_data,
    )
    # check if they're gone
    sight_cf_rsp = conf_utils.read_main_settings(
        flask_app_client, admin_user, 'site.custom.customFields.Sighting'
    ).json
    definitions = sight_cf_rsp['response']['value']['definitions']
    def_ids = [defi['id'] for defi in definitions]
    assert first['id'] not in def_ids
    assert second['id'] not in def_ids


def test_dict_write(flask_app_client, admin_user):
    # Create json site setting
    data = [
        {'label': 'Matriarch', 'multipleInGroup': False},
        {'label': 'IrritatingGit', 'multipleInGroup': True},
    ]

    resp = conf_utils.modify_main_settings(
        flask_app_client, admin_user, {'_value': data}, 'social_group_roles'
    )

    assert resp.json['key'] == 'social_group_roles'

    conf_utils.delete_main_setting(flask_app_client, admin_user, 'social_group_roles')


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_alter_houston_settings(flask_app_client, admin_user, researcher_1):

    username = 'noone@nowhere.com'
    password = 'VeryPrivateThing'
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': username},
        'email_service_username',
    )
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': password},
        'email_service_password',
    )
    config_def_response_admin = conf_utils.read_main_settings_definition(
        flask_app_client, admin_user, 'block'
    )
    config_def_response_researcher = conf_utils.read_main_settings_definition(
        flask_app_client, researcher_1, '__bundle_setup'
    )
    config_response_admin = conf_utils.read_main_settings(
        flask_app_client, admin_user, 'block'
    )
    config_response_researcher = conf_utils.read_main_settings(
        flask_app_client, researcher_1, '__bundle_setup'
    )

    # admin should be able to see uname & pass, researcher should not.
    admin_configuration = config_response_admin.json['response']['configuration']
    admin_definition = config_def_response_admin.json['response']['configuration']
    researcher_configuration = config_response_researcher.json['response'][
        'configuration'
    ]
    researcher_definition = config_def_response_researcher.json['response'][
        'configuration'
    ]

    assert admin_configuration['email_service_username']['value'] == username
    assert admin_configuration['email_service_username']['valueNotSet'] is False
    assert admin_configuration['email_service_password']['value'] == password
    assert admin_configuration['email_service_password']['valueNotSet'] is False
    assert 'email_service_username' not in researcher_configuration
    assert 'email_service_password' not in researcher_configuration
    assert 'currentValue' not in researcher_definition['email_service_username']
    assert 'currentValue' not in researcher_definition['email_service_password']
    assert admin_definition['email_service_username']['currentValue'] == username
    assert admin_definition['email_service_password']['currentValue'] == password

    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': None},
        'email_service_username',
    )
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': None},
        'email_service_password',
    )
    config_response_admin = conf_utils.read_main_settings(
        flask_app_client, admin_user, 'block'
    )
    admin_configuration = config_response_admin.json['response']['configuration']

    assert admin_configuration['email_service_username']['value'] is None
    assert admin_configuration['email_service_username']['valueNotSet']
    assert admin_configuration['email_service_password']['value'] is None
    assert admin_configuration['email_service_password']['valueNotSet']
