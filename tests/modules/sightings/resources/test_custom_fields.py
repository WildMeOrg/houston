# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils
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
    request,
):
    import datetime

    from app.modules.sightings.models import Sighting

    cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'test_cfd', cls='Sighting'
    )
    assert cfd_id is not None
    cfd_multi_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'test_multi_cfd', multiple=True, cls='Sighting'
    )
    assert cfd_multi_id is not None

    timestamp = datetime.datetime.now().isoformat() + '+00:00'
    # transaction_id, test_filename = sighting_utils.prep_tus_dir(test_root)
    cfd_test_value = 'CFD_TEST_VALUE'
    cfd_multi_value = ['one', 'two']
    data_in = {
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': str(uuid.uuid4()),
        'customFields': {
            cfd_id: cfd_test_value,
            cfd_multi_id: cfd_multi_value,
        },
        'encounters': [{}],
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        data_in,
    )

    sighting_id = uuids['sighting']
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
            'guid': str(encounter.guid),
            'hasEdit': True,
            'hasView': True,
            'created': encounter.created.isoformat() + '+00:00',
            'updated': encounter.updated.isoformat() + '+00:00',
            'owner': {
                'full_name': encounter.owner.full_name,
                'guid': str(encounter.owner.guid),
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
            'guid': str(sighting.guid),
            'hasEdit': True,
            'hasView': True,
            'locationId': sighting.location_guid,
            'comments': None,
            'encounters': encounters,
            'created': sighting.created.isoformat() + '+00:00',
            'updated': sighting.updated.isoformat() + '+00:00',
            'assets': assets,
            'featuredAssetGuid': str(sighting.featured_asset_guid),
            'customFields': {
                cfd_id: cfd_test_value,
                cfd_multi_id: cfd_multi_value,
            },
            # Only asserting that these fields exist
            'time': full_sighting.json['time'],
            'timeSpecificity': full_sighting.json['timeSpecificity'],
        }
    )

    # for some reason the assert above *passes* even though cfd_multi_value is wrong (maybe the >=)
    # so lets check this manually
    assert 'customFields' in full_sighting.json
    assert cfd_id in full_sighting.json['customFields']
    assert cfd_multi_id in full_sighting.json['customFields']
    assert full_sighting.json['customFields'][cfd_id] == cfd_test_value
    assert full_sighting.json['customFields'][cfd_multi_id] == cfd_multi_value

    # test patch on customFields
    new_cfd_test_value = 'NEW_CFD_TEST_VALUE'
    new_cfd_multi_value = ['A', 'B']
    sighting_utils.patch_sighting(
        flask_app_client,
        researcher_1,
        sighting_id,
        patch_data=[
            {
                'op': 'replace',
                'path': '/customFields',
                'value': {'id': cfd_id, 'value': new_cfd_test_value},
            },
            {
                'op': 'replace',
                'path': '/customFields',
                'value': {'id': cfd_multi_id, 'value': new_cfd_multi_value},
            },
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
    assert cfd_multi_id in full_sighting.json['customFields']
    assert full_sighting.json['customFields'][cfd_multi_id] == new_cfd_multi_value

    # now since we have some values in use, lets make sure we cannot delete the definition
    res = setting_utils.patch_main_setting(
        flask_app_client,
        admin_user,
        '',
        [
            {
                'path': 'site.custom.customFields.Sighting/' + cfd_id,
                'op': 'remove',
            }
        ],
        400,
    )
    assert 'in use by' in res.json['message']
