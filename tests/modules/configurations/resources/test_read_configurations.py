# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests.modules.configurations.resources import utils as conf_utils

CONFIG_PATH = '/api/v1/configuration/default'
CONFIG_DEF_PATH = '/api/v1/configurationDefinition/default'


def test_read_configurations(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    test_key = 'site.name'
    response = conf_utils.read_configuration(flask_app_client, researcher_1, test_key)
    assert 'response' in response.json
    assert response.json['response']['id'] == test_key
    response = conf_utils.read_configuration_definition(
        flask_app_client, researcher_1, test_key
    )
    assert 'response' in response.json
    assert response.json['response']['configurationId'] == test_key
    assert response.json['response']['fieldType'] == 'string'

    # a bad key
    response = conf_utils.read_configuration(
        flask_app_client, researcher_1, '__INVALID_KEY__', expected_status_code=400
    )
    assert not response.json['success']

    from app.modules.ia_config_reader import IaConfig

    ia_config_reader = IaConfig()
    species = ia_config_reader.get_configured_species()
    config_def_response = conf_utils.read_configuration_definition(
        flask_app_client, researcher_1, 'site.species'
    )
    # note: this relies on IaConfig and get_configured_species() not changing too radically
    assert len(config_def_response.json['response']['suggestedValues']) >= len(species)
    for i in range(len(species)):
        assert (
            config_def_response.json['response']['suggestedValues'][i]['scientificName']
            == species[len(species) - i - 1]
        )

    config_def_response = conf_utils.read_configuration_definition(
        flask_app_client, researcher_1, '__bundle_setup'
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


def test_alter_configurations(flask_app_client, admin_user):
    response = conf_utils.read_configuration(flask_app_client, admin_user, 'site.species')
    assert 'response' in response.json
    assert 'value' in response.json['response']
    vals = response.json['response']['value']
    vals.append({'commonNames': ['Test data'], 'scientificName': 'Testus datum'})
    response = conf_utils.modify_configuration(
        flask_app_client,
        admin_user,
        'site.species',
        {'_value': vals},
    )
    response = conf_utils.read_configuration(flask_app_client, admin_user, 'site.species')
    assert 'response' in response.json
    assert 'value' in response.json['response']
    assert response.json['response']['value'][-1]['scientificName'] == 'Testus datum'
    # restore original list
    vals.pop()
    response = conf_utils.modify_configuration(
        flask_app_client,
        admin_user,
        'site.species',
        {'_value': vals},
    )
