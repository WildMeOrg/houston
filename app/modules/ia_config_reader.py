# -*- coding: utf-8 -*-

import logging
import json
import os.path as path

log = logging.getLogger(__name__)


# detects @-links in values from any level of the ia config
def _is_link(config_value):
    is_link = type(config_value) is str and config_value.startswith('@')
    return is_link


# simply takes the '@' off the beginning of a link
def _link_destination(link_str):
    destination = link_str.split('@')[1]
    return destination


class IaConfig:
    def __init__(self, name='zebra'):
        self.name = name
        self.fname = f'IA.{name}.json'
        config_path = path.join('ia-configs', self.fname)
        assert path.isfile(config_path), f'Could not find config at path {config_path}'
        with open(config_path, 'r') as file:
            self.config_dict = json.load(file)

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
        species_key = genus_species.replace(' ', '.')
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
        species_key = genus_species.replace(' ', '.')
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
        return identifiers_dict

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
        species_key = genus_species.replace(' ', '.')
        ia_classes = [key for key in self.get(species_key) if not key.startswith('_')]
        return ia_classes

    # Do we want this to be resilient to missing fields, like return None or ""
    # if an itis-id is missing? Current thinking is, if we're using those fields
    # on the frontend they are required, so this would error if they are missing.
    def get_frontend_species_summary(self, genus_species):
        species_key = genus_species.replace(' ', '.')
        summary_dict = {
            'scientific_name': genus_species,
            'common_name': self.get(f'{species_key}._common_name'),
            'itis_id': self.get(f'{species_key}._itis_id'),
            'ia_classes': self.get_supported_ia_classes(genus_species),
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
