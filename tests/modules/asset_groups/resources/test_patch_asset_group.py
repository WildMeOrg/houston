# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid
import copy

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.annotations.resources.utils as annot_utils
from tests import utils
import pytest

from tests.utils import module_unavailable


# Test a bunch of failure scenarios
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_asset_group(
    flask_app_client, researcher_1, regular_user, test_root, db, empty_individual, request
):
    # pylint: disable=invalid-name

    (
        asset_group_guid,
        asset_group_sighting_guid,
        asset_guid,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, regular_user, request, test_root
    )

    # Regular user can create it but not read it??????
    asset_group_utils.read_asset_group_sighting(
        flask_app_client, regular_user, asset_group_sighting_guid, 403
    )

    # Researcher should be able to
    group_sighting = asset_group_utils.read_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid
    )
    assert 'completion' in group_sighting.json
    assert group_sighting.json['completion'] == 10
    assert 'config' in group_sighting.json
    assert 'assetReferences' in group_sighting.json['config']

    new_absent_file = copy.deepcopy(group_sighting.json['config']['assetReferences'])
    new_absent_file.append('absent_file.jpg')
    patch_data = [utils.patch_replace_op('assetReferences', new_absent_file)]
    expected_resp = (
        f'absent_file.jpg not in Group for assetGroupSighting {asset_group_sighting_guid}'
    )
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
        patch_data,
        400,
        expected_resp,
    )

    # Valid patch, adding a new encounter
    patch_data = [utils.patch_add_op('encounters', {})]

    # Should not work as contributor
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client, regular_user, asset_group_sighting_guid, patch_data, 403
    )

    # should work as researcher
    patch_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid, patch_data
    )
    assert len(patch_resp.json['config']['encounters']) == 2

    # chosen for reasons of incongruity as the naked mole rat is virtually blind
    # so has no 'sight'
    add_name_patch = [utils.patch_add_op('name', 'Naked Mole Rat')]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid, add_name_patch
    )

    # invalid patch, encounter has individualuuid of nonsense
    encounter_guid = group_sighting.json['config']['encounters'][0]['guid']
    encounter_path = f'{asset_group_sighting_guid}/encounter/{encounter_guid}'

    patch_data = [utils.patch_add_op('individualUuid', '8037460')]
    expected_resp = f'Encounter {encounter_guid} individual 8037460 not valid'
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, encounter_path, patch_data, 400, expected_resp
    )

    # invalid patch, encounter has invalid individualuuid
    invalid_uuid = str(uuid.uuid4())

    patch_data = [utils.patch_add_op('individualUuid', invalid_uuid)]
    expected_resp = f'Encounter {encounter_guid} individual {invalid_uuid} not found'
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, encounter_path, patch_data, 400, expected_resp
    )

    # valid patch, real individual
    with db.session.begin():
        db.session.add(empty_individual)
    request.addfinalizer(lambda: db.session.delete(empty_individual))
    patch_data = [utils.patch_add_op('individualUuid', str(empty_individual.guid))]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        patch_data,
    )

    # Valid patch, removing the added encounter
    guid_to_go = patch_resp.json['config']['encounters'][-1]['guid']
    patch_remove = [utils.patch_remove_op('encounters', guid_to_go)]
    patch_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid, patch_remove
    )
    assert len(patch_resp.json['config']['encounters']) == 1

    # invalid patch, encounter has invalid annotation uuid
    patch_data = [utils.patch_add_op('annotations', invalid_uuid)]
    expected_resp = f'Encounter {encounter_guid} annotation:{invalid_uuid} not found'
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, encounter_path, patch_data, 400, expected_resp
    )

    annot_response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_guid,
    )

    annotation_guid = annot_response.json['guid']

    # Attempt to replace which should fail
    patch_replace_annot = [utils.patch_replace_op('annotations', annotation_guid)]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        patch_replace_annot,
        409,
    )

    # Add annot, should succeed
    patch_annot = [utils.patch_add_op('annotations', annotation_guid)]
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, encounter_path, patch_annot
    )
    annots = annot_add_resp.json['config']['encounters'][0]['annotations']
    assert len(annots) == 1
    assert annots[0] == annotation_guid


# similar to the above but against the AGS-as-sighting endpoint
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_asset_group_sighting_as_sighting(
    flask_app_client, researcher_1, regular_user, test_root, request
):
    # pylint: disable=invalid-name
    from tests import utils

    (
        asset_group_uuid,
        asset_group_sighting_guid,
        asset_guid,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, regular_user, request, test_root
    )

    # Regular user can create it but not read it??????
    asset_group_utils.read_asset_group_sighting_as_sighting(
        flask_app_client, regular_user, asset_group_sighting_guid, 403
    )

    # Researcher should be able to
    group_sighting = asset_group_utils.read_asset_group_sighting_as_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid
    )

    # startTime and locationId are only present in the _as_sighting endpoints,
    # since they are in the config of a standard AGS
    for field in {'id', 'stage', 'completion', 'assets', 'startTime', 'locationId'}:
        assert field in group_sighting.json

    assert group_sighting.json['asset_group_guid'] == asset_group_uuid
    assert group_sighting.json['creator']['guid'] == str(regular_user.guid)

    # Valid patch, adding a new encounter
    patch_data = [utils.patch_add_op('encounters', {})]

    # Should not work as contributor
    asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client, regular_user, asset_group_sighting_guid, patch_data, 403
    )

    # should work as researcher
    asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid, patch_data
    )

    # chosen for reasons of incongruity as the naked mole rat is virtually blind
    # so has no 'sight'
    add_name_patch = [utils.patch_add_op('name', 'Naked Mole Rat')]
    response = asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid, add_name_patch
    )

    # Patch encounter in asset group sighting
    encounter_guids = [e['guid'] for e in response.json['encounters']]

    # Set first encounter sex to male
    response = asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_1,
        f'{asset_group_sighting_guid}/encounter/{encounter_guids[0]}',
        [utils.patch_replace_op('sex', 'male')],
    )
    assert [e['sex'] for e in response.json['encounters']] == ['male', None]

    # Set first encounter sex to null
    response = asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_1,
        f'{asset_group_sighting_guid}/encounter/{encounter_guids[0]}',
        [utils.patch_replace_op('sex', None)],
    )
    assert [e['sex'] for e in response.json['encounters']] == [None, None]
