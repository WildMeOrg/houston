# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils
from tests.extensions.edm import utils as edm_utils
from tests.modules.configuration.resources import utils as conf_utils
import pytest
import random
import json

from tests.utils import module_unavailable, random_decimal_latitude, random_decimal_longitude


@pytest.mark.skipif(
    module_unavailable('encounters', 'sightings'),
    reason='Encounters and Sightings modules disabled',
)
def test_mega_data(
    db,
    flask_app_client,
    researcher_1,
    admin_user,
):
    from app.modules.sightings.models import Sighting
    import datetime

    # make some customFields in edm
    sighting_cfd_id = edm_utils.custom_field_create(
        flask_app_client, admin_user, 'occ_test_cfd'
    )
    assert sighting_cfd_id is not None
    encounter_cfd_id = edm_utils.custom_field_create(
        flask_app_client, admin_user, 'enc_test_cfd', cls='Encounter'
    )
    assert encounter_cfd_id is not None

    # make us a taxonomy to use in edm
    response = conf_utils.read_configuration(flask_app_client, admin_user, 'site.species')
    assert 'value' in response.json['response']
    vals = response.json['response']['value']
    vals.append({'commonNames': ['Example'], 'scientificName': 'Exempli gratia'})
    response = conf_utils.modify_configuration(
        flask_app_client,
        admin_user,
        'site.species',
        {'_value': vals},
    )
    response = conf_utils.read_configuration(flask_app_client, admin_user, 'site.species')
    assert 'response' in response.json and 'value' in response.json['response']
    tx_guid = response.json['response']['value'][-1]['id']

    sighting_timestamp_start = datetime.datetime.now().isoformat() + 'Z'
    sighting_timestamp_end = (
        datetime.datetime.now() + datetime.timedelta(hours=1)
    ).isoformat() + 'Z'
    encounter_timestamp = datetime.datetime.now().isoformat() + 'Z'
    cfd_test_value = 'CFD_TEST_VALUE'

    encounter_data_in = {
        'time': encounter_timestamp,
        'locationId': 'enc-test',
        'taxonomy': {'id': tx_guid},
        'decimalLatitude': random_decimal_latitude(),
        'decimalLongitude': random_decimal_longitude(),
        'country': 'TEST',
        'sex': 'male',
        'customFields': {
            encounter_cfd_id: cfd_test_value,
        },
    }

    sighting_data_in = {
        'startTime': sighting_timestamp_start,
        'endTime': sighting_timestamp_end,
        'locationId': 'sig-test',
        'decimalLatitude': random_decimal_latitude(),
        'decimalLongitude': random_decimal_longitude(),
        'bearing': random.uniform(0, 180),
        'distance': random.uniform(1, 100),
        'customFields': {
            sighting_cfd_id: cfd_test_value,
        },
        'encounters': [encounter_data_in],
        'taxonomies': [{'id': tx_guid}],
    }
    response = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        sighting_data_in,
    )

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    full_sighting = sighting_utils.read_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
    )

    # so we can capture the example if we want, via -s flag on pytest
    print(json.dumps(full_sighting.json, indent=4, sort_keys=True))

    # some checks on response
    assert (
        full_sighting.json['startTime'][0:18] == sighting_timestamp_start[0:18]
    )  # grr rounding/precision
    assert full_sighting.json['endTime'][0:18] == sighting_timestamp_end[0:18]
    assert 'customFields' in full_sighting.json
    assert sighting_cfd_id in full_sighting.json['customFields']
    assert full_sighting.json['customFields'][sighting_cfd_id] == cfd_test_value
    assert (
        'encounters' in full_sighting.json and len(full_sighting.json['encounters']) == 1
    )
    assert full_sighting.json['encounters'][0]['taxonomy']['id'] == tx_guid
    assert full_sighting.json['encounters'][0]['time'][0:18] == encounter_timestamp[0:18]
    assert encounter_cfd_id in full_sighting.json['encounters'][0]['customFields']
    assert (
        full_sighting.json['encounters'][0]['customFields'][encounter_cfd_id]
        == cfd_test_value
    )

    # clean up
    sighting_utils.delete_sighting(flask_app_client, researcher_1, sighting_id)
