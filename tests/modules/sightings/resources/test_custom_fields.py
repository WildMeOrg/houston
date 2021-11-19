# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils
from tests.extensions.edm import utils as edm_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_custom_fields_on_sighting(
    db,
    flask_app_client,
    researcher_1,
    test_root,
    staff_user,
    admin_user,
    test_asset_group_uuid,
):
    from app.modules.sightings.models import Sighting
    import datetime

    cfd_id = edm_utils.custom_field_create(flask_app_client, admin_user, 'test_cfd')
    assert cfd_id is not None

    timestamp = datetime.datetime.now().isoformat() + 'Z'
    transaction_id, test_filename = sighting_utils.prep_tus_dir(test_root)
    cfd_test_value = 'CFD_TEST_VALUE'
    data_in = {
        'startTime': timestamp,
        'locationId': 'test',
        'customFields': {
            cfd_id: cfd_test_value,
        },
        'encounters': [{}],
    }
    response = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        data_in,
    )

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    # Attach some assets
    from app.modules.asset_groups.models import AssetGroup

    assets = AssetGroup.query.get(test_asset_group_uuid).assets
    sighting.add_assets(assets)

    full_sighting = sighting_utils.read_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
    )

    encounters = [
        {
            'customFields': {},
            'timeValues': [None, None, None, 0, 0],
            'id': str(encounter.guid),
            'guid': str(encounter.guid),
            'hasEdit': True,
            'hasView': True,
            'version': encounter.version,
            'createdHouston': encounter.created.isoformat() + '+00:00',
            'updatedHouston': encounter.updated.isoformat() + '+00:00',
            'owner': {
                'full_name': encounter.owner.full_name,
                'guid': str(encounter.owner.guid),
                'profile_fileupload': None,
            },
            'submitter': {
                'full_name': encounter.submitter.full_name,
                'guid': str(encounter.submitter.guid),
                'profile_fileupload': None,
            },
        }
        for encounter in sighting.encounters
    ]

    assets = [
        {
            'guid': str(asset.guid),
            'filename': asset.filename,
            'src': asset.src,
            'annotations': [],
            'dimensions': asset.get_dimensions(),
            'created': asset.created.isoformat() + '+00:00',
            'updated': asset.updated.isoformat() + '+00:00',
        }
        for asset in sighting.get_assets()
    ]

    # make sure customFields value is actually set
    assert set(full_sighting.json) >= set(
        {
            'id': str(sighting.guid),
            'guid': str(sighting.guid),
            'hasEdit': True,
            'hasView': True,
            'locationId': 'test',
            'comments': 'None',
            'encounters': encounters,
            'encounterCounts': {'sex': {}, 'individuals': 0},
            'version': sighting.version,
            'createdHouston': sighting.created.isoformat() + '+00:00',
            'updatedHouston': sighting.updated.isoformat() + '+00:00',
            'assets': assets,
            'featuredAssetGuid': str(sighting.featured_asset_guid),
            'customFields': {cfd_id: cfd_test_value},
            # Only asserting that these fields exist
            'startTime': full_sighting.json['startTime'],
            'createdEDM': full_sighting.json['createdEDM'],
        }
    )

    # test patch on customFields
    new_cfd_test_value = 'NEW_CFD_TEST_VALUE'
    sighting_utils.patch_sighting(
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
