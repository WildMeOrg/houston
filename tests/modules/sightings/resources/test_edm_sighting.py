# -*- coding: utf-8 -*-

import tests.modules.sightings.resources.utils as sighting_utils
import pytest
import datetime

from tests.utils import module_unavailable


timestamp = datetime.datetime.now().isoformat() + '+00:00'


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_edm_patch_add(db, flask_app_client, researcher_1, request, test_root):

    data_in = {
        'encounters': [{}, {}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'context': 'test',
        'locationId': 'test',
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )

    sighting_id = uuids['sighting']
    longitude = 24.9999

    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {'op': 'add', 'path': '/decimalLongitude', 'value': longitude},
        ],
    )

    response = sighting_utils.read_sighting(flask_app_client, researcher_1, sighting_id)

    assert response.json['decimalLongitude'] == longitude
