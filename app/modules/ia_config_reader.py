# -*- coding: utf-8 -*-

import logging
import json
import os.path as path

log = logging.getLogger(__name__)


def load_config_to_dict(fname):
    app_home = ''
    config_path = path.join(app_home, 'ia-configs', fname)
    assert path.isfile(config_path), f'Could not find config at path {config_path}'
    with open(config_path, 'r') as file:
        config_dict = json.load(file)
    return config_dict


def short_config_name_to_full_filename(config_name):
    fname = f'IA.{config_name}.json'
    return fname


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
        self.fname = short_config_name_to_full_filename(self.name)
        self.config_dict = load_config_to_dict(self.fname)

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
