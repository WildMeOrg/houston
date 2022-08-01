# -*- coding: utf-8 -*-

import copy
import json
import logging
import os.path as path
import pathlib

log = logging.getLogger(__name__)


# detects @-links in values from any level of the ia config
def _is_link(config_value):
    is_link = type(config_value) is str and config_value.startswith('@')
    return is_link


# simply takes the '@' off the beginning of a link
def _link_destination(link_str):
    destination = link_str.split('@')[1]
    return destination


# gets the lookup key for a taxonomy string
def _get_species_key(genus_species):
    # only replace first space, because additional spaces indicate 'species subspecies' which is a single key with a space. This allows us to distinguish between a subspecies and an ia class under a species.
    key = genus_species.replace(' ', '.', 1)
    return key


# recursive version of python dict.update
def recurse_update(dict1, dict2):
    for key, val in dict2.items():
        if isinstance(val, dict):
            dict1[key] = recurse_update(dict1.get(key, {}), val)
        elif isinstance(val, list):
            dict1[key] = dict1.get(key, []) + val
        else:
            dict1[key] = val
    return dict1


class IaConfig:
    def __init__(self):
        # self.name = name
        # self.fname = f'IA.{name}.json'
        # config_path = path.jpytest -s tests/modules/test_ia_config.py::test_get_seal_detectors --no-elasticsearchoin('ia-configs', self.fname)
        # assert path.isfile(config_path), f'Could not find config at path {config_path}'
        # with open(config_path, 'r') as file:
        #     self.config_dict = json.load(file)
        self.config_dict = {}
        for conf_fpath in pathlib.Path('ia-configs').glob('IA.*.json'):
            with open(conf_fpath, 'r') as file:
                _conf_dict = json.load(file)
                self.config_dict = recurse_update(self.config_dict, _conf_dict)


    def get(self, period_separated_keys):
        keys = period_separated_keys.split('.')
        return self.get_recursive(keys, self.config_dict)

    def get_recursive(self, keys, config_dict_level):
        current_key = keys[0]
        current_value = config_dict_level[current_key]
        is_base_case = len(keys) == 1

        # following @-links
        if _is_link(current_value):
            # resolve the link destination. It will look like an unlinked current_value.
            current_value = self.get(_link_destination(current_value))
        # base case, no link
        if is_base_case:
            value = current_value
        # recursive case
        else:
            next_keys = keys[1:]
            value = self.get_recursive(next_keys, current_value)
        return value

    def get_named_detector_config(self, detector_name):
        detector_config = self.get(f'_detectors.{detector_name}.config_dict')
        return detector_config

    def get_detectors_with_links(self, genus_species):
        species_key = _get_species_key(genus_species)
        detectors_key = f'{species_key}._detectors'
        detectors = self.get(detectors_key)
        return detectors

    def get_detectors_list(self, genus_species):
        detectors = self.get_detectors_with_links(genus_species)
        detectors_list = self._resolve_links_in_value_list(detectors)
        return detectors_list

    def get_detectors_dict(self, genus_species):
        detectors = self.get_detectors_with_links(genus_species)
        detectors_dict = self._resolve_links_to_dict(detectors)
        return detectors_dict

    def get_identifiers_with_links(self, genus_species, ia_class):
        species_key = _get_species_key(genus_species)
        identifiers_key = f'{species_key}.{ia_class}._identifiers'
        identifiers = self.get(identifiers_key)
        return identifiers

    def get_identifiers_list(self, genus_species, ia_class):
        identifiers = self.get_identifiers_with_links(genus_species, ia_class)
        identifiers_list = self._resolve_links_in_value_list(identifiers)
        return identifiers_list

    def get_identifiers_dict(self, genus_species, ia_class):
        identifiers = self.get_identifiers_with_links(genus_species, ia_class)
        identifiers_dict = self._resolve_links_to_dict(identifiers)
        # trim the '_identifiers.' prefix off the keys
        trimmed = dict()
        for key in identifiers_dict:
            algo = key
            if key.startswith('_identifiers.'):
                algo = key[13:]
            trimmed[algo] = identifiers_dict[key]
        return trimmed

    def _resolve_links_in_value_list(self, value_list):
        resolved_list = [
            self.get(_link_destination(value)) if _is_link(value) else value
            for value in value_list
        ]
        return resolved_list

    # takes a list of links, returns a dict mapping those links to their resolved values
    def _resolve_links_to_dict(self, link_list):
        resolved_dicts = {
            _link_destination(link): self.get(_link_destination(link))
            for link in link_list
        }
        return resolved_dicts

    def get_configured_species(self):
        genuses = [key for key in self.config_dict.keys() if not key.startswith('_')]
        species = []
        for genus in genuses:
            spec_epithets = [key for key in self.get(genus) if not key.startswith('_')]
            genus_species = [f'{genus} {species}' for species in spec_epithets]
            species += genus_species
        return species

    def get_supported_ia_classes(self, genus_species):
        species_key = _get_species_key(genus_species)
        ia_classes = [key for key in self.get(species_key) if not key.startswith('_')]
        return ia_classes

    def get_all_ia_classes(self):
        all_species = self.get_configured_species()
        all_ia_classes = set()
        for specie in all_species:
            all_ia_classes = all_ia_classes | set(self.get_supported_ia_classes(specie))
        all_ia_classes = list(all_ia_classes)
        all_ia_classes.sort()
        return all_ia_classes

    def get_supported_id_algos(self, genus_species, ia_classes=None):
        if ia_classes is None:
            ia_classes = self.get_supported_ia_classes(genus_species)
        ia_algos = dict()
        for ia_class in ia_classes:
            algo_dict = copy.deepcopy(self.get_identifiers_dict(genus_species, ia_class))
            # so one can modify the returned dicts without modifying this class's config dict
            algo_dict = copy.deepcopy(algo_dict)
            ia_algos.update(algo_dict)
        return ia_algos

    # Do we want this to be resilient to missing fields, like return None or ""
    # if an itis-id is missing? Current thinking is, if we're using those fields
    # on the frontend they are required, so this would error if they are missing.
    def get_frontend_species_summary(self, genus_species):
        species_key = _get_species_key(genus_species)
        id_algos = self.get_supported_id_algos(genus_species)
        for algo in id_algos:
            id_algos[algo] = id_algos[algo]['frontend']
        summary_dict = {
            'scientific_name': genus_species,
            'common_name': self.get(f'{species_key}._common_name'),
            'itis_id': self.get(f'{species_key}._itis_id'),
            'ia_classes': self.get_supported_ia_classes(genus_species),
            'id_algos': id_algos,
        }
        return summary_dict

    # for populating a frontend list of detector options
    def get_detect_model_frontend_data(self):
        detectors = self.get('_detectors')
        specieses = self.get_configured_species()
        detector_to_species = {det_key: [] for det_key in detectors.keys()}
        # build detector_to_species map
        for species in specieses:
            _detectors_dict = self.get_detectors_dict(species)
            _detectors_name_list = [
                key.replace('_detectors.', '') for key in _detectors_dict
            ]
            for _detector in _detectors_name_list:
                detector_to_species[_detector].append(species)

        result = {}
        for key, config in detectors.items():
            result[key] = {
                'name': config['name'],
                'description': config['description'],
                'supported_species': [
                    self.get_frontend_species_summary(spec)
                    for spec in detector_to_species[key]
                ],
            }
        return result


# ic = IaConfig()

# ic.get_detect_model_frontend_data()
