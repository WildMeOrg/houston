# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils

CONFIG_PATH = '/api/v1/configuration/default'
CONFIG_DEF_PATH = '/api/v1/configurationDefinition/default'


def test_read_configurations(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    with flask_app_client.login(researcher_1, auth_scopes=('configuration:read',)):
        config_response = flask_app_client.get('%s/site.name' % CONFIG_PATH)
        config_def_response = flask_app_client.get('%s/site.name' % CONFIG_DEF_PATH)

    utils.validate_dict_response(config_response, 200, {'success', 'response'})
    utils.validate_dict_response(config_def_response, 200, {'success', 'response'})
