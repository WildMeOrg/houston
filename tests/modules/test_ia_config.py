# -*- coding: utf-8 -*-

from app.modules.ia_config_reader import IaConfig

# note that these tests rely on the IA.zebra.json file, which if changed, might invalidate tests.
TEST_CONFIG_NAME = 'zebra'


def test_ia_config_creation(flask_app_client):
    config_name = TEST_CONFIG_NAME
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    assert ia_config_reader.name is config_name
    assert ia_config_reader.fname.endswith('.json')
    assert type(ia_config_reader.config_dict) is dict


def test_at_links_detector(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    nolink_quagga_detectors = ia_config_reader.get_detectors_dict('Equus quagga')
    # grevy config links to quagga config
    linked_grevy_detectors = ia_config_reader.get_detectors_dict('Equus grevyi')
    assert nolink_quagga_detectors == linked_grevy_detectors


def test_at_links_identifier(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    nolink_zebra_ia_class = ia_config_reader.get_identifiers_dict('Equus quagga', 'zebra')
    # below species/ia_class links to config for above with two levels of linking
    linked_grevy_ia_class = ia_config_reader.get_identifiers_dict(
        'Equus grevyi', 'zebra_grevys'
    )
    assert nolink_zebra_ia_class == linked_grevy_ia_class


def test_detector_dict_vs_link(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    species = 'Equus quagga'
    detectors_list = ia_config_reader.get_detectors_list(species)
    detectors_dict = ia_config_reader.get_detectors_dict(species)
    detectors_dict_values = detectors_dict.values()

    dict_items_in_list = [val in detectors_list for val in detectors_dict_values]
    list_items_in_dict = [val in detectors_dict_values for val in detectors_list]

    assert all(dict_items_in_list)
    assert all(list_items_in_dict)


def test_identifier_dict_vs_link(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    species = 'Equus quagga'
    ia_class = 'zebra'
    identifiers_list = ia_config_reader.get_identifiers_list(species, ia_class)
    identifiers_dict = ia_config_reader.get_identifiers_dict(species, ia_class)
    identifiers_dict_values = identifiers_dict.values()

    dict_items_in_list = [val in identifiers_list for val in identifiers_dict_values]
    list_items_in_dict = [val in identifiers_dict_values for val in identifiers_list]

    assert all(dict_items_in_list)
    assert all(list_items_in_dict)


def test_get_identifiers_zebras(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    species = 'Equus quagga'
    ia_class = 'zebra'
    identifiers = ia_config_reader.get_identifiers_dict(species, ia_class)

    # copy/pasted from the config and pythonified (vs json)
    desired_identifiers = {
        'hotspotter_nosv': {
            'sage': {'query_config_dict': {'sv_on': False}},
            'frontend': {'description': 'HotSpotter pattern-matcher'},
        }
    }
    assert identifiers == desired_identifiers


def test_get_detectors_zebras(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    species = 'Equus quagga'
    detectors = ia_config_reader.get_detectors_dict(species)

    desired_detectors = {
        '_detectors.african_terrestrial': {
            'name': 'African terrestrial mammal detector',
            'description': 'Trained on zebras, giraffes, lions, hyenas, leopards, cheetahs, and wild dogs.',
            'config_dict': {
                'start_detect': '/api/engine/detect/cnn/lightnet/',
                'labeler_algo': 'densenet',
                'labeler_model_tag': 'zebra_v1',
                'model_tag': 'ggr2',
                'nms_thresh': 0.4,
                'sensitivity': 0.4,
            },
        }
    }
    assert detectors == desired_detectors


def test_get_named_detector_config_african_terrestrial(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    detector_name = 'african_terrestrial'
    detector_config = ia_config_reader.get_named_detector_config(detector_name)

    desired_config = {
        'start_detect': '/api/engine/detect/cnn/lightnet/',
        'labeler_algo': 'densenet',
        'labeler_model_tag': 'zebra_v1',
        'model_tag': 'ggr2',
        'nms_thresh': 0.4,
        'sensitivity': 0.4,
    }
    assert detector_config == desired_config


def test_get_configured_species(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    species = ia_config_reader.get_configured_species()
    desired_species = ['Equus grevyi', 'Equus quagga']
    assert species == desired_species


def test_get_detect_model_frontend_data(flask_app_client):
    ia_config_reader = IaConfig(TEST_CONFIG_NAME)
    desired_frontend_data = {
        'african_terrestrial': {
            'name': 'African terrestrial mammal detector',
            'description': 'Trained on zebras, giraffes, lions, hyenas, leopards, cheetahs, and wild dogs.',
            'supported_species': [
                {
                    'scientific_name': 'Equus grevyi',
                    'common_name': "Grevy's zebra",
                    'itis_id': 202400,
                    'ia_classes': ['zebra_grevys', 'zebra'],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'scientific_name': 'Equus quagga',
                    'common_name': 'plains zebra',
                    'itis_id': 624996,
                    'ia_classes': ['zebra_grevys', 'zebra'],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
            ],
        }
    }
    frontend_data = ia_config_reader.get_detect_model_frontend_data()
    assert frontend_data == desired_frontend_data
