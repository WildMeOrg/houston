# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import json

import pytest

from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils
from tests.utils import (
    module_unavailable,
    random_decimal_latitude,
    random_decimal_longitude,
)


@pytest.mark.skipif(
    module_unavailable('encounters', 'sightings'),
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
    import datetime

    from app.modules.sightings.models import Sighting

    # make some customFields in edm
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

    sighting_timestamp = datetime.datetime.now().isoformat() + '+00:00'
    encounter_timestamp = datetime.datetime.now().isoformat() + '+00:00'
    cfd_test_value = 'CFD_TEST_VALUE'

    encounter_data_in = {
        'time': encounter_timestamp,
        'timeSpecificity': 'time',
        'locationId': 'enc-test',
        'taxonomy': tx_guid,
        'decimalLatitude': random_decimal_latitude(),
        'decimalLongitude': random_decimal_longitude(),
        'sex': 'male',
        'customFields': {
            encounter_cfd_id: cfd_test_value,
        },
    }

    sighting_data_in = {
        'time': sighting_timestamp,
        'timeSpecificity': 'time',
        'locationId': 'sig-test',
        'decimalLatitude': random_decimal_latitude(),
        'decimalLongitude': random_decimal_longitude(),
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
