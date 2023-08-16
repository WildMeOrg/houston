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
    'Pusa hispida',
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
            'sage': {'query_config_dict': {'sv_on': True}},
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
        'seals_v1': {
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
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
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
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
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
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
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
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'scientific_name': 'Pusa hispida',
                    'common_name': 'ringed seal',
                    'itis_id': 622018,
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
                    },
                },
                {
                    'common_name': 'Baltic ringed seal',
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 622062,
                    'scientific_name': 'Pusa hispida botnica',
                },
                {
                    'common_name': 'Arctic ringed seal',
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 622061,
                    'scientific_name': 'Pusa hispida hispida',
                },
                {
                    'common_name': 'Okhotsk ringed seal',
                    'ia_classes': [
                        'grey_seal_femaleyoung',
                        'grey_seal_male',
                        'grey_seal_pup',
                        'grey_seal_unknown',
                        'harbour_seal',
                        'hawaiian_monk_seal',
                        'mediterranean_monk_seal',
                        'seal',
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 622065,
                    'scientific_name': 'Pusa hispida ' 'ochontensis',
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
                        'seal_ringed',
                    ],
                    'id_algos': {
                        'hotspotter_nosv': {'description': 'HotSpotter pattern-matcher'}
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
        'deer_model_v0': {
            'description': 'Deer detector v0 using efficientnet',
            'name': 'Deer model v0 detector',
            'supported_species': [
                {
                    'common_name': 'Chital deer',
                    'ia_classes': ['deer_unknown'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 2440934,
                    'scientific_name': 'Axis axis',
                },
                {
                    'common_name': 'Sika deer',
                    'ia_classes': ['deer_unknown'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 2440954,
                    'scientific_name': 'Cervus nippon',
                },
                {
                    'common_name': 'Fallow deer',
                    'ia_classes': ['deer_unknown'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5220136,
                    'scientific_name': 'Dama dama',
                },
                {
                    'common_name': 'White-tailed deer',
                    'ia_classes': ['deer_unknown'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 2440965,
                    'scientific_name': 'Odocoileus ' 'virginianus',
                },
                {
                    'common_name': "Eld's deer",
                    'ia_classes': ['deer_unknown'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': -999996223,
                    'scientific_name': 'Rucervis eldii',
                },
                {
                    'common_name': 'Visayan spotted deer',
                    'ia_classes': ['deer_unknown'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 4262394,
                    'scientific_name': 'Rusa alfredi',
                },
            ],
        },
        'snail_v0': {
            'description': 'Snail detector (v0) with orientation plugin',
            'name': 'snail_v0 detector',
            'supported_species': [
                {
                    'common_name': 'Oahu Treesnail',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 7342715,
                    'scientific_name': 'Achatinella ' 'apexfulva',
                },
                {
                    'common_name': 'Achatinella bulimoides',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 7342713,
                    'scientific_name': 'Achatinella ' 'bulimoides',
                },
                {
                    'common_name': 'Achatinella byronii',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782908,
                    'scientific_name': 'Achatinella byronii',
                },
                {
                    'common_name': 'Achatinella concavospira',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782925,
                    'scientific_name': 'Achatinella ' 'concavospira',
                },
                {
                    'common_name': 'Achatinella decipiens',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782913,
                    'scientific_name': 'Achatinella ' 'decipiens',
                },
                {
                    'common_name': 'Achatinella fulgens',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782902,
                    'scientific_name': 'Achatinella fulgens',
                },
                {
                    'common_name': 'Achatinella fuscobasis',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782923,
                    'scientific_name': 'Achatinella ' 'fuscobasis',
                },
                {
                    'common_name': 'Achatinella lila',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782904,
                    'scientific_name': 'Achatinella lila',
                },
                {
                    'common_name': 'Achatinella livida',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782929,
                    'scientific_name': 'Achatinella livida',
                },
                {
                    'common_name': 'Achatinella mustelina',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782912,
                    'scientific_name': 'Achatinella ' 'mustelina',
                },
                {
                    'common_name': 'Achatinella sowerbyana',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782930,
                    'scientific_name': 'Achatinella ' 'sowerbyana',
                },
                {
                    'common_name': 'Auriculela ambusta',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': -9999375494,
                    'scientific_name': 'Auriculela ambusta',
                },
                {
                    'common_name': 'Laminella sanguinea',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5783136,
                    'scientific_name': 'Laminella sanguinea',
                },
                {
                    'common_name': 'Laminella venusta',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 8912654,
                    'scientific_name': 'Laminella venusta',
                },
                {
                    'common_name': 'Newcombia canaliculata',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 8997851,
                    'scientific_name': 'Newcombia ' 'canaliculata',
                },
                {
                    'common_name': 'Newcombia cumingi',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782948,
                    'scientific_name': 'Newcombia cumingi',
                },
                {
                    'common_name': 'Partlulina species',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': -9999201464,
                    'scientific_name': 'Partlulina species',
                },
                {
                    'common_name': 'Fat Guam Partula',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5783059,
                    'scientific_name': 'Partula gibba',
                },
                {
                    'common_name': 'Partula lutaensis (Rota)',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': -9999457578,
                    'scientific_name': 'Partula ' 'lutaensis_rota',
                },
                {
                    'common_name': 'Radiolate Partula',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782998,
                    'scientific_name': 'Partula radiolata',
                },
                {
                    'common_name': 'Partulina anceyana',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 11146968,
                    'scientific_name': 'Partulina anceyana',
                },
                {
                    'common_name': 'Partulina crocea',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 10681979,
                    'scientific_name': 'Partulina crocea',
                },
                {
                    'common_name': 'Partulina fusoidea',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782880,
                    'scientific_name': 'Partulina fusoidea',
                },
                {
                    'common_name': 'Partulina induta',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 9145302,
                    'scientific_name': 'Partulina induta',
                },
                {
                    'common_name': 'Partulina marmorata',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 9049386,
                    'scientific_name': 'Partulina marmorata',
                },
                {
                    'common_name': 'Partulina mighelsiana',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782887,
                    'scientific_name': 'Partulina ' 'mighelsiana',
                },
                {
                    'common_name': 'Partulina perdix',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782890,
                    'scientific_name': 'Partulina perdix',
                },
                {
                    'common_name': 'Partulina physa',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782886,
                    'scientific_name': 'Partulina physa',
                },
                {
                    'common_name': 'Partulina porcellana',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782884,
                    'scientific_name': 'Partulina porcellana',
                },
                {
                    'common_name': 'Partulina proxima',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782895,
                    'scientific_name': 'Partulina proxima',
                },
                {
                    'common_name': 'Partulina redfieldi',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782883,
                    'scientific_name': 'Partulina redfieldi',
                },
                {
                    'common_name': 'Partulina semicarinata',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782894,
                    'scientific_name': 'Partulina ' 'semicarinata',
                },
                {
                    'common_name': 'Splendid Partulina',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782877,
                    'scientific_name': 'Partulina splendida',
                },
                {
                    'common_name': 'Partulina tappaniana',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782893,
                    'scientific_name': 'Partulina tappaniana',
                },
                {
                    'common_name': 'Partulina tesselata',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': -9999671394,
                    'scientific_name': 'Partulina tesselata',
                },
                {
                    'common_name': 'Partulina variabilis',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782891,
                    'scientific_name': 'Partulina variabilis',
                },
                {
                    'common_name': 'Partulina virgulata',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 4597942,
                    'scientific_name': 'Partulina virgulata',
                },
                {
                    'common_name': 'Perdicella helena',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782859,
                    'scientific_name': 'Perdicella helena',
                },
                {
                    'common_name': 'Perdicella ornata',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782853,
                    'scientific_name': 'Perdicella ornata',
                },
                {
                    'common_name': 'Perdicella zebra',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5782852,
                    'scientific_name': 'Perdicella zebra',
                },
                {
                    'common_name': 'Fragile tree snail',
                    'ia_classes': ['snail'],
                    'id_algos': {
                        'hotspotter_nosv': {
                            'description': 'HotSpotter ' 'pattern-matcher'
                        }
                    },
                    'itis_id': 5783090,
                    'scientific_name': 'Samoana fragilis',
                },
            ],
        },
    }
    frontend_data = ia_config_reader.get_detect_model_frontend_data()
    assert desired_frontend_data == frontend_data


def test_get_seal_ia_classes(flask_app_client):
    ia_config_reader = IaConfig()
    frontend_data = ia_config_reader.get_detect_model_frontend_data()
    desired_ia_classes = {
        'grey_seal_femaleyoung',
        'grey_seal_male',
        'grey_seal_pup',
        'grey_seal_unknown',
        'harbour_seal',
        'hawaiian_monk_seal',
        'mediterranean_monk_seal',
        'seal',
        'seal_ringed',
    }
    ia_classes = set()
    for species in frontend_data['seals_v1']['supported_species']:
        ia_classes = ia_classes | set(species['ia_classes'])
    assert ia_classes == desired_ia_classes


def test_get_seal_species(flask_app_client):
    ia_config_reader = IaConfig()
    species = ia_config_reader.get_configured_species()
    assert set(SEAL_SPECIES) <= set(species)


def test_get_seal_detectors(flask_app_client):
    ia_config_reader = IaConfig()
    desired_detector_config = {
        '_detectors.seals_v1': {
            'config_dict': {
                'labeler_algo': 'densenet',
                'labeler_model_tag': 'seals_v1',
                'model_tag': 'seals_v1',
                'nms_aware': 'ispart',
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
        'hotspotter_nosv': {
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
