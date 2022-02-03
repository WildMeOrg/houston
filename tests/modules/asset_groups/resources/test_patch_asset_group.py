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

    annotation1_guid = annot_response.json['guid']

    annot_response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_guid,
    )
    annotation2_guid = annot_response.json['guid']

    # Attempt to replace which should pass
    annot_replace_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        [utils.patch_replace_op('annotations', annotation1_guid)],
    )
    annots = annot_replace_resp.json['config']['encounters'][0]['annotations']
    assert len(annots) == 1
    assert annots[0] == annotation1_guid

    # Add annot, should succeed
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        [utils.patch_add_op('annotations', annotation2_guid)],
    )
    annots = annot_add_resp.json['config']['encounters'][0]['annotations']
    assert len(annots) == 2
    assert annots[1] == annotation2_guid

    # adding it again should have no effect
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        [utils.patch_add_op('annotations', annotation2_guid)],
    )
    annots = annot_add_resp.json['config']['encounters'][0]['annotations']
    assert len(annots) == 2
    assert annots[1] == annotation2_guid


# similar to the above but against the AGS-as-sighting endpoint
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_asset_group_sighting_as_sighting(
    flask_app_client, researcher_1, researcher_2, regular_user, test_root, request
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

    # time and locationId are only present in the _as_sighting endpoints,
    # since they are in the config of a standard AGS
    for field in {
        'guid',
        'stage',
        'completion',
        'assets',
        'time',
        'timeSpecificity',
        'locationId',
    }:
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
    encounter_patch_fields = {
        'version',
        'hasView',
        'hasEdit',
        'guid',
        'owner',
        'updatedHouston',
        'createdHouston',
        'submitter',
    }

    response = asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_1,
        f'{asset_group_sighting_guid}/encounter/{encounter_guids[0]}',
        [utils.patch_replace_op('sex', 'male')],
        response_200=encounter_patch_fields,
    )
    assert response.json['sex'] == 'male'

    # Set first encounter sex to null
    response = asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_1,
        f'{asset_group_sighting_guid}/encounter/{encounter_guids[0]}',
        [utils.patch_replace_op('sex', None)],
        response_200=encounter_patch_fields,
    )
    assert response.json['sex'] is None

    # Reassign to researcher2 via email
    response = asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_1,
        f'{asset_group_sighting_guid}/encounter/{encounter_guids[0]}',
        [utils.patch_add_op('ownerEmail', researcher_2.email)],
        response_200=encounter_patch_fields,
    )

    assert response.json['owner']['guid'] == str(researcher_2.guid)

    # And back to researcher 1 by guid
    response = asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_2,
        f'{asset_group_sighting_guid}/encounter/{encounter_guids[0]}',
        [utils.patch_replace_op('owner', str(researcher_1.guid))],
        response_200=encounter_patch_fields,
    )
    assert response.json['owner']['guid'] == str(researcher_1.guid)


# specifically for DEX-644
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_annotation_in_asset_group(
    flask_app_client, researcher_1, regular_user, test_root, db, empty_individual, request
):
    # pylint: disable=invalid-name
    from tests.modules.annotations.resources import utils as annot_utils

    (
        asset_group_guid,
        asset_group_sighting_guid,
        asset_guid,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, regular_user, request, test_root
    )

    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_guid,
    )
    annotation_guid = response.json['guid']

    group_sighting = asset_group_utils.read_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
    )
    assert group_sighting.json['assets']
    assert len(group_sighting.json['assets'][0]['annotations']) == 1
    assert group_sighting.json['assets'][0]['annotations'][0]['guid'] == annotation_guid
    assert 'bounds' in group_sighting.json['assets'][0]['annotations'][0]
    assert 'rect' in group_sighting.json['assets'][0]['annotations'][0]['bounds']
    assert group_sighting.json['assets'][0]['annotations'][0]['bounds']['rect'] == [
        0,
        1,
        2,
        3,
    ]


# specifically for DEX-660
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_time_ags_encounters(
    flask_app_client, researcher_1, regular_user, test_root, db, empty_individual, request
):

    (
        asset_group_guid,
        asset_group_sighting_guid,
        asset_guid,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, regular_user, request, test_root
    )

    group_sighting = asset_group_utils.read_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
    )
    encounter_guid = group_sighting.json['config']['encounters'][0]['guid']
    assert encounter_guid

    # patch time value on encounter
    encounter_path = f'{asset_group_sighting_guid}/encounter/{encounter_guid}'
    time_value = '2000-01-01T01:01:01+00:00'
    patch_data = [
        utils.patch_add_op('time', time_value),
        utils.patch_add_op('timeSpecificity', 'month'),
    ]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        patch_data,
    )

    # now verify change
    group_sighting_verify = asset_group_utils.read_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
    )
    assert group_sighting_verify.json['config']['encounters'][0]['time'] == time_value
    assert (
        group_sighting_verify.json['config']['encounters'][0]['timeSpecificity']
        == 'month'
    )


# moving annot from one encounter to the other
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_asset_group_annots(
    flask_app_client, researcher_1, regular_user, test_root, db, empty_individual, request
):
    # pylint: disable=invalid-name

    # Using bulk creation data means we get an AGS with two encounters which is what we need to add the annot to
    # the first one and then move it to the second
    data = asset_group_utils.get_bulk_creation_data(test_root, request)
    resp = asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get()
    )
    asset_group_uuid = resp.json['guid']

    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_uuid
        )
    )
    ags_guid = resp.json['asset_group_sightings'][0]['guid']
    encounter_guids = [
        enc['guid']
        for enc in resp.json['asset_group_sightings'][0]['config']['encounters']
    ]
    assert len(encounter_guids) == 2
    encounter1_path = f'{ags_guid}/encounter/{encounter_guids[0]}'
    encounter2_path = f'{ags_guid}/encounter/{encounter_guids[1]}'

    ags_asset_name = resp.json['asset_group_sightings'][0]['config']['assetReferences'][0]
    asset_guids = [
        asset['guid']
        for asset in resp.json['assets']
        if asset['filename'] == ags_asset_name
    ]
    assert len(asset_guids) == 1

    response = annot_utils.create_annotation_simple(
        flask_app_client,
        researcher_1,
        asset_guids[0],
    )

    annotation_guid = response.json['guid']

    # Add annot, should succeed
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter1_path,
        [utils.patch_add_op('annotations', annotation_guid)],
    )
    enc1_annots = annot_add_resp.json['config']['encounters'][0]['annotations']
    assert len(enc1_annots) == 1
    assert enc1_annots[0] == annotation_guid

    # Add annot to enc 2, should remove it from enc 1
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter2_path,
        [utils.patch_add_op('annotations', annotation_guid)],
    )

    enc1_annots = annot_add_resp.json['config']['encounters'][0]['annotations']
    enc2_annots = annot_add_resp.json['config']['encounters'][1]['annotations']
    assert len(enc1_annots) == 0
    assert len(enc2_annots) == 1
    assert enc2_annots[0] == annotation_guid
