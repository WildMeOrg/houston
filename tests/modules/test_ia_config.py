# -*- coding: utf-8 -*-
from app.modules.ia_config_reader import IaConfig

# note that these tests rely on the IA.zebra.json file, which if changed, might invalidate tests.
TEST_CONFIG_NAME = 'zebra'


def test_ia_config_creation(flask_app_client):

    config_name = TEST_CONFIG_NAME
    ia_config_reader = IaConfig(config_name)
    assert ia_config_reader.name is config_name
    assert ia_config_reader.fname.endswith('.json')
    assert type(ia_config_reader.config_dict) is dict


def test_at_links(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    nolink_quagga_detectors = ia_config_reader.get_detectors_dict('Equus quagga')
    # grevy config links to quagga config
    linked_grevy_detectors = ia_config_reader.get_detectors_dict('Equus grevyi')
    assert nolink_quagga_detectors == linked_grevy_detectors


def test_detector_dict_vs_link(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    species = 'Equus quagga'
    detectors_list = ia_config_reader.get_detectors_dict(species)
    detectors_dict = ia_config_reader.get_detectors_list(species)
    detectors_dict_values = detectors_dict.values()

    dict_items_in_list = [val in detectors_list for val in detectors_dict_values]
    list_items_in_dict = [val in detectors_dict_values for val in detectors_list]

    assert all(dict_items_in_list)
    assert all(list_items_in_dict)


def test_config_to_filename(flask_app_client):
    from app.modules.ia_config_reader import short_config_name_to_full_filename

    config_name = 'zebra'
    filename = short_config_name_to_full_filename(config_name)
    assert filename == 'IA.zebra.json'


def test_loading_config_dict(flask_app_client):
    from app.modules.ia_config_reader import short_config_name_to_full_filename
    from app.modules.ia_config_reader import load_config_to_dict

    config_name = 'zebra'
    filename = short_config_name_to_full_filename(config_name)
    config_dict = load_config_to_dict(filename)

    assert type(config_dict) is dict

    desired_keys = {'_README', '_detectors', '_identifiers', 'Equus'}
    for key in desired_keys:
        assert key in config_dict.keys()
