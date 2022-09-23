# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.encounters.resources.utils as enc_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.modules.site_settings.resources.utils as site_setting_utils
import tests.utils as test_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_use_collaboration(
    flask_app_client, researcher_1, researcher_2, admin_user, test_root, db, request
):
    from app.modules.collaborations.models import Collaboration

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    asset_group_uuid = uuids['asset_group']
    sighting_guid = uuids['sighting']
    asset_guid = uuids['assets'][0]
    enc_guid = uuids['encounters'][0]
    data = {
        'user_guid': str(researcher_1.guid),
    }

    collab_utils.create_collaboration(flask_app_client, researcher_2, data)
    collabs = Collaboration.query.all()
    collab = collabs[0]
    request.addfinalizer(lambda: collab.delete())

    asset_group_utils.read_asset_group(
        flask_app_client, researcher_2, asset_group_uuid, 403
    )
    collab.set_approval_state_for_user(researcher_1.guid, 'approved')

    # Researcher 2 should be able to view all the data but edit none of it
    asset_group_utils.read_asset_group(flask_app_client, researcher_2, asset_group_uuid)
    asset_group_utils.read_asset_group_sighting(
        flask_app_client, researcher_2, uuids['asset_group_sighting']
    )
    asset_utils.read_asset(flask_app_client, researcher_2, asset_guid)
    enc_utils.read_encounter(flask_app_client, researcher_2, enc_guid)
    sighting_utils.read_sighting(flask_app_client, researcher_2, sighting_guid)

    # test an 'owner' example
    tx = site_setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    assert tx
    assert 'id' in tx
    taxonomy_guid = tx['id']
    enc_patch = [
        test_utils.patch_replace_op('taxonomy', taxonomy_guid),
    ]
    expected_err = f'You have permission to view but not edit Encounter {enc_guid}. '
    expected_err += f'You will need to upgrade your collaboration with {researcher_1.full_name} to an edit collaboration to do so'
    enc_utils.patch_encounter(
        flask_app_client, enc_guid, researcher_2, enc_patch, 403, expected_err
    )

    # Test a get_owner example
    asset_patch = [
        {
            'op': 'replace',
            'path': '/image',
            'value': {'rotate': {'angle': -90}},
        },
    ]
    expected_err = f'You have permission to view but not edit Asset {asset_guid}. '
    expected_err += f'You will need to upgrade your collaboration with {researcher_1.full_name} to an edit collaboration to do so'

    asset_utils.patch_asset(
        flask_app_client, uuids['assets'][0], researcher_2, asset_patch, 403, expected_err
    )

    # Test sighting as something with get_owners
    sighting_patch = [
        test_utils.patch_replace_op('featuredAssetGuid', '%s' % asset_guid),
    ]

    sighting_patch_resp = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_2,
        sighting_guid,
        sighting_patch,
        expected_status_code=403,
    )
    expected_err = f'You have permission to view but not edit Sighting {sighting_guid}. '
    expected_err += f'You will need to upgrade your collaboration with {researcher_1.full_name} to an edit collaboration to do so'
    assert sighting_patch_resp.json['message'] == expected_err
