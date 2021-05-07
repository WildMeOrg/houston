# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils
from tests.extensions.edm import utils as edm_utils
from tests import utils as test_utils


CONFIG_PATH = '/api/v1/configuration/default'


def test_custom_fields_on_sighting(
    db, flask_app_client, researcher_1, test_root, staff_user, admin_user
):
    from app.modules.sightings.models import Sighting
    from app.modules.encounters.models import Encounter
    from app.modules.assets.models import Asset
    from app.modules.asset_groups.models import AssetGroup
    import datetime

    cfd_id = edm_utils.custom_field_create(flask_app_client, admin_user, 'test_cfd')
    assert cfd_id is not None

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))

    timestamp = datetime.datetime.now().isoformat()
    transaction_id, test_filename = sighting_utils.prep_tus_dir(test_root)
    cfd_test_value = 'CFD_TEST_VALUE'
    data_in = {
        'startTime': timestamp,
        'context': 'test',
        'locationId': 'test',
        'customFields': {
            cfd_id: cfd_test_value,
        },
        'encounters': [{}],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=200, data_in=data_in
    )
    assert response.json['success']

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None
    full_sighting = sighting_utils.read_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
    )
    # make sure customFields value is actually set
    assert 'customFields' in full_sighting.json
    assert cfd_id in full_sighting.json['customFields']
    assert full_sighting.json['customFields'][cfd_id] == cfd_test_value

    # test patch on customFields
    new_cfd_test_value = 'NEW_CFD_TEST_VALUE'
    response = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {
                'op': 'replace',
                'path': '/customFields',
                'value': {'id': cfd_id, 'value': new_cfd_test_value},
            }
        ],
    )
    assert response.json['success']
    # check that change was made
    full_sighting = sighting_utils.read_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
    )
    # make sure customFields value has been altered
    assert 'customFields' in full_sighting.json
    assert cfd_id in full_sighting.json['customFields']
    assert full_sighting.json['customFields'][cfd_id] == new_cfd_test_value

    # clean up
    sighting_utils.delete_sighting(flask_app_client, researcher_1, sighting_id)

    post_ct = test_utils.multi_count(db, (Sighting, Encounter, Asset, AssetGroup))
    assert orig_ct == post_ct
