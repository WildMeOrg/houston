# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils
from tests.modules.configurations.resources import utils as conf_utils
import json

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
    with flask_app_client.login(researcher_1, auth_scopes=('configuration:read',)):
        # config_response = flask_app_client.get('%s/site.species' % CONFIG_PATH)
        config_def_response = flask_app_client.get('%s/site.species' % CONFIG_DEF_PATH)
    utils.validate_dict_response(config_def_response, 200, {'success', 'response'})
    # note: this relies on IaConfig and get_configured_species() not changing too radically
    assert len(config_def_response.json['response']['suggestedValues']) >= len(species)
    for i in range(len(species)):
        assert (
            config_def_response.json['response']['suggestedValues'][i]['scientificName']
            == species[len(species) - i - 1]
        )

    with flask_app_client.login(researcher_1, auth_scopes=('configuration:read',)):
        # config_response = flask_app_client.get('%s/__bundle_setup' % CONFIG_PATH)
        config_def_response = flask_app_client.get('%s/__bundle_setup' % CONFIG_DEF_PATH)
    utils.validate_dict_response(config_def_response, 200, {'success', 'response'})
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


def test_alter_configurations(flask_app_client, researcher_1, admin_user):
    with flask_app_client.login(researcher_1, auth_scopes=('configuration:read',)):
        response = flask_app_client.post(
            '%s' % CONFIG_PATH,
            data=json.dumps({'site.general.description': 'Testing as researcher_1.'}),
            content_type='application/json',
        )
    assert response.status_code == 401  # researcher cannot do this

    with flask_app_client.login(admin_user, auth_scopes=('configuration:write',)):
        response = flask_app_client.post(
            '%s' % CONFIG_PATH,
            data=json.dumps({'site.general.description': 'Testing as admin.'}),
            content_type='application/json',
        )

    utils.validate_dict_response(
        response, 200, {'success', 'updated'}
    )  # admin can set config
    assert response.json['success']
