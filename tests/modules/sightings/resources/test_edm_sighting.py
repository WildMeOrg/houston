# -*- coding: utf-8 -*-
import pytest

import tests.modules.sightings.resources.utils as sighting_utils
from tests import utils as test_utils
from tests.utils import module_unavailable

timestamp = test_utils.isoformat_timestamp_now()


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_patch_add(db, flask_app_client, researcher_1, request, test_root):

    data_in = {
        'encounters': [{}, {}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )

    sighting_id = uuids['sighting']
    longitude = 24.9999
    latitude = 45.9999

    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'add', 'path': '/decimalLongitude', 'value': longitude},
            {'op': 'replace', 'path': '/decimalLatitude', 'value': latitude},
        ],
    )

    response = sighting_utils.read_sighting(flask_app_client, researcher_1, sighting_id)
    assert response.json['decimalLongitude'] == longitude
    assert response.json['decimalLatitude'] == latitude
