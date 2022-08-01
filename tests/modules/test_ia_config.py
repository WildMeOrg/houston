# -*- coding: utf-8 -*-

from app.modules.ia_config_reader import IaConfig

# These tests validate not only the parsing code but config files themselves
# When you add a new config file, add parsing tests here akin to seals

SEAL_SPECIES = [
    'Halichoerus grypus',
    'Monachus monachus',
    'Neomonachus schauinslandi',
    'Phoca vitulina',
    'Pusa hispida saimensis',
]


def test_ia_config_creation(flask_app_client):
    ia_config_reader = IaConfig()
    assert type(ia_config_reader.config_dict) is dict


def test_at_links_detector(flask_app_client):
    ia_config_reader = IaConfig()
    nolink_quagga_detectors = ia_config_reader.get_detectors_dict('Equus quagga')
    # grevy config links to quagga config
    linked_grevy_detectors = ia_config_reader.get_detectors_dict('Equus grevyi')
    assert nolink_quagga_detectors == linked_grevy_detectors


def test_at_links_identifier(flask_app_client):
    ia_config_reader = IaConfig()
    nolink_zebra_ia_class = ia_config_reader.get_identifiers_dict('Equus quagga', 'zebra')
    # below species/ia_class links to config for above with two levels of linking
    linked_grevy_ia_class = ia_config_reader.get_identifiers_dict(
        'Equus grevyi', 'zebra_grevys'
    )
    assert nolink_zebra_ia_class == linked_grevy_ia_class


def test_detector_dict_vs_link(flask_app_client):
    ia_config_reader = IaConfig()
    species = 'Equus quagga'
    detectors_list = ia_config_reader.get_detectors_list(species)
    detectors_dict = ia_config_reader.get_detectors_dict(species)
    detectors_dict_values = detectors_dict.values()

    dict_items_in_list = [val in detectors_list for val in detectors_dict_values]
    list_items_in_dict = [val in detectors_dict_values for val in detectors_list]

    assert all(dict_items_in_list)
    assert all(list_items_in_dict)


def test_identifier_dict_vs_link(flask_app_client):
    ia_config_reader = IaConfig()
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
    ia_config_reader = IaConfig()
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
    ia_config_reader = IaConfig()
    species = 'Equus quagga'
    detectors = ia_config_reader.get_detectors_dict(species)

    desired_detectors = {
        '_detectors.african_terrestrial': {
            'name': 'African terrestrial mammal detector',
            'description': 'Trained on zebras, giraffes, lions, hyenas, leopards, cheetahs, and wild dogs.',
            'config_dict': {
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
    ia_config_reader = IaConfig()
    detector_name = 'african_terrestrial'
    detector_config = ia_config_reader.get_named_detector_config(detector_name)

    desired_config = {
        'labeler_algo': 'densenet',
        'labeler_model_tag': 'zebra_v1',
        'model_tag': 'ggr2',
        'nms_thresh': 0.4,
        'sensitivity': 0.4,
    }
    assert detector_config == desired_config


def test_get_zebra_species(flask_app_client):
    ia_config_reader = IaConfig()
    species = ia_config_reader.get_configured_species()
    desired_species = ['Equus grevyi', 'Equus quagga']
    assert desired_species <= species


def test_get_detect_model_frontend_data(flask_app_client):
    ia_config_reader = IaConfig()
    desired_frontend_data = {
        'seals_v0': {
            'name': 'Seal detector',
            'description': 'Trained on grey seals, harbor seals, hawaiian monk seals, and mediterranean monk seals',
            'supported_species': [
                {
                    'scientific_name': 'Halichoerus grypus',
                    'common_name': 'gray seal',
                    'itis_id': 180653,
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                    ],
                    'id_algos': {
                        'hotspotter': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'scientific_name': 'Monachus monachus',
                    'common_name': 'Mediterranean monk seal',
                    'itis_id': 180659,
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                    ],
                    'id_algos': {
                        'hotspotter': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'scientific_name': 'Neomonachus schauinslandi',
                    'common_name': 'Hawaiian monk seal',
                    'itis_id': 1133135,
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                    ],
                    'id_algos': {
                        'hotspotter': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'scientific_name': 'Phoca vitulina',
                    'common_name': 'harbor seal',
                    'itis_id': 180649,
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                    ],
                    'id_algos': {
                        'hotspotter': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'scientific_name': 'Pusa hispida saimensis',
                    'common_name': 'Saimaa seal',
                    'itis_id': 622064,
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                        'seal',
                    ],
                    'id_algos': {
                        'hotspotter': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
            ],
        },
        'african_terrestrial': {
            'name': 'African terrestrial mammal detector',
            'description': 'Trained on zebras, giraffes, lions, hyenas, leopards, cheetahs, and wild dogs.',
            'supported_species': [
                {
                    'scientific_name': 'Equus grevyi',
                    'common_name': "Grevy's zebra",
                    'itis_id': 202400,
                    'ia_classes': ['zebra', 'zebra_grevys'],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'scientific_name': 'Equus quagga',
                    'common_name': 'plains zebra',
                    'itis_id': 624996,
                    'ia_classes': ['zebra', 'zebra_grevys'],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
            ],
        },
    }
    frontend_data = ia_config_reader.get_detect_model_frontend_data()
    assert desired_frontend_data == frontend_data


def test_get_seal_species(flask_app_client):
    ia_config_reader = IaConfig()
    species = ia_config_reader.get_configured_species()
    assert set(SEAL_SPECIES) <= set(species)


def test_get_seal_detectors(flask_app_client):
    ia_config_reader = IaConfig()
    desired_detector_config = {
        '_detectors.seals_v0': {
            'config_dict': {
                'labeler_algo': 'densenet',
                'labeler_model_tag': 'seals_v0',
                'model_tag': 'seals_v0',
                'nms_aware': None,
                'nms_thresh': 0.4,
                'sensitivity': 0.63,
                'use_labeler_species': True,
            },
            'name': 'Seal detector',
            'description': 'Trained on grey seals, harbor seals, hawaiian monk seals, and mediterranean monk seals',
        }
    }
    for species in SEAL_SPECIES:
        detector = ia_config_reader.get_detectors_dict(species)
        assert detector == desired_detector_config


def test_get_seal_identifiers(flask_app_client):
    ia_config_reader = IaConfig()
    desired_identifier_config = {
        'hotspotter': {
            'frontend': {'description': 'HotSpotter pattern-matcher'},
            'sage': {'query_config_dict': {'sv_on': True}},
        }
    }
    # each seal species, for each supported ia_class, should use the same hotspotter config
    for species in SEAL_SPECIES:
        ia_classes = ia_config_reader.get_supported_ia_classes(species)
        for ia_class in ia_classes:
            identifiers = ia_config_reader.get_identifiers_dict(species, ia_class)
            assert identifiers == desired_identifier_config
