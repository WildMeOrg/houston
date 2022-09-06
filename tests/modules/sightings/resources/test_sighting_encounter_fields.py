# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import json

import pytest

from tests import utils as test_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils


@pytest.mark.skipif(
    test_utils.module_unavailable('encounters', 'sightings'),
    reason='Encounters and Sightings modules disabled',
)
def test_mega_data(
    db,
    flask_app_client,
    researcher_1,
    admin_user,
    request,
    test_root,
):
    from app.modules.sightings.models import Sighting

    # make some customFields
    sighting_cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'occ_test_cfd'
    )
    assert sighting_cfd_id is not None
    encounter_cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'enc_test_cfd', cls='Encounter'
    )
    assert encounter_cfd_id is not None

    # make us a taxonomy to use in edm
    response = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    tx_guid = response['id']

    sighting_timestamp = test_utils.isoformat_timestamp_now()
    encounter_timestamp = test_utils.isoformat_timestamp_now()
    cfd_test_value = 'CFD_TEST_VALUE'
    location_id = test_utils.get_valid_location_id()
    lat = test_utils.random_decimal_latitude()
    long = test_utils.random_decimal_longitude()
    encounter_data_in = {
        'time': encounter_timestamp,
        'timeSpecificity': 'time',
        'locationId': location_id,
        'taxonomy': tx_guid,
        'decimalLatitude': lat,
        'decimalLongitude': long,
        'sex': 'male',
        'customFields': {
            encounter_cfd_id: cfd_test_value,
        },
    }

    sighting_data_in = {
        'time': sighting_timestamp,
        'timeSpecificity': 'time',
        'locationId': location_id,
        'decimalLatitude': lat,
        'decimalLongitude': long,
        'customFields': {
            sighting_cfd_id: cfd_test_value,
        },
        'encounters': [encounter_data_in],
        'taxonomies': [tx_guid],
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data_in,
    )

    sighting_id = uuids['sighting']
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
        full_sighting.json['time'][0:18] == sighting_timestamp[0:18]
    )  # grr rounding/precision
    assert 'customFields' in full_sighting.json
    assert sighting_cfd_id in full_sighting.json['customFields']
    assert full_sighting.json['customFields'][sighting_cfd_id] == cfd_test_value
    assert (
        'encounters' in full_sighting.json and len(full_sighting.json['encounters']) == 1
    )
    assert full_sighting.json['encounters'][0]['taxonomy'] == tx_guid
    assert full_sighting.json['encounters'][0]['time'][0:18] == encounter_timestamp[0:18]
    assert encounter_cfd_id in full_sighting.json['encounters'][0]['customFields']
    assert (
        full_sighting.json['encounters'][0]['customFields'][encounter_cfd_id]
        == cfd_test_value
    )
