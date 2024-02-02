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
    from app.modules.sightings.models import Sighting

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    asset_group_uuid = uuids['asset_group']
    sighting_guid = uuids['sighting']
    asset_guid = uuids['assets'][0]
    enc_guid = uuids['encounters'][0]
    sighting = Sighting.query.get(sighting_guid)

    assert sighting.user_has_view_permission(researcher_1)
    assert sighting.user_has_export_permission(researcher_1)
    assert not sighting.user_has_view_permission(researcher_2)
    assert not sighting.user_has_export_permission(researcher_2)

    # should not work and should give informative error
    ags_resp = asset_group_utils.read_asset_group_sighting(
        flask_app_client, researcher_2, uuids['asset_group_sighting'], 403
    ).json
    access_error = f"You do not have permission to view AssetGroupSighting {uuids['asset_group_sighting']}. "
    access_error += (
        f'To do this, you need a view collaboration with {researcher_1.full_name}'
    )
    assert ags_resp['message'] == access_error

    # create a (view) collab and approve
    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)
    request.addfinalizer(collab.delete)
    collab_utils.approve_view_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    assert sighting.user_has_view_permission(researcher_1)
    assert sighting.user_has_export_permission(researcher_1)
    assert sighting.user_has_view_permission(researcher_2)
    assert sighting.user_has_export_permission(researcher_2)

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
    expected_err = f'You do not have permission to edit Encounter {enc_guid}. '
    expected_err += (
        f'To do this, you need an edit collaboration with {researcher_1.full_name}'
    )
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
    expected_err = f'You do not have permission to edit Asset {asset_guid}. '
    expected_err += (
        f'To do this, you need an edit collaboration with {researcher_1.full_name}'
    )

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
    expected_err = f'You do not have permission to edit Sighting {sighting_guid}. '
    expected_err += (
        f'To do this, you need an edit collaboration with {researcher_1.full_name}'
    )
    assert sighting_patch_resp.json['message'] == expected_err

    # Researcher 1 requests that this is escalated to an export collaboration
    collab_utils.request_export_simple_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )
    # which is approved
    collab_utils.approve_export_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    assert sighting.user_has_view_permission(researcher_1)
    assert sighting.user_has_export_permission(researcher_1)
    assert sighting.user_has_view_permission(researcher_2)
    assert sighting.user_has_export_permission(researcher_2)

    # Researcher 1 requests that this is escalated to an edit collaboration
    collab_utils.request_edit_simple_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )
    # which is approved
    collab_utils.approve_edit_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # now this should work due to edit collab
    sighting_patch_resp = sighting_utils.patch_sighting(
        flask_app_client,
        researcher_2,
        sighting_guid,
        sighting_patch,
    )
