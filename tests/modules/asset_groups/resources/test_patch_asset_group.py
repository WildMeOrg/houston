# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import copy
import uuid

import pytest

import tests.modules.annotations.resources.utils as annot_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
from tests import utils
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
    assert 'config' in group_sighting.json
    assert 'assetReferences' in group_sighting.json['config']['sighting']

    new_absent_file = copy.deepcopy(
        group_sighting.json['config']['sighting']['assetReferences']
    )
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
    patch_data = [utils.patch_replace_op('time', None)]
    expected_resp = "Failed to update AssetGroupSighting details. Operation OrderedDict([('op', 'replace'), ('path', '/time'), ('value', None), ('field_name', 'time')]) could not succeed."

    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
        patch_data,
        409,
        expected_resp,
    )

    patch_data = [utils.patch_replace_op('time', '2020-05-01T00:00:00+01:00')]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
        patch_data,
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
    assert len(patch_resp.json['config']['sighting']['encounters']) == 2

    # chosen for reasons of incongruity as the naked mole rat is virtually blind
    # so has no 'sight'
    add_name_patch = [utils.patch_add_op('name', 'Naked Mole Rat')]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid, add_name_patch
    )

    # invalid patch, encounter has individualuuid of nonsense
    encounter_guid = group_sighting.json['config']['sighting']['encounters'][0]['guid']
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
    guid_to_go = patch_resp.json['config']['sighting']['encounters'][-1]['guid']
    patch_remove = [utils.patch_remove_op('encounters', guid_to_go)]
    patch_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid, patch_remove
    )
    assert len(patch_resp.json['config']['sighting']['encounters']) == 1

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
    annots = annot_replace_resp.json['config']['sighting']['encounters'][0]['annotations']
    assert len(annots) == 1
    assert annots[0] == annotation1_guid

    # Add annot, should succeed
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        [utils.patch_add_op('annotations', annotation2_guid)],
    )
    annots = annot_add_resp.json['config']['sighting']['encounters'][0]['annotations']
    assert len(annots) == 2
    assert annots[1] == annotation2_guid

    # adding it again should have no effect
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        [utils.patch_add_op('annotations', annotation2_guid)],
    )
    annots = annot_add_resp.json['config']['sighting']['encounters'][0]['annotations']
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
        'hasView',
        'hasEdit',
        'guid',
        'owner',
        'updated',
        'created',
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


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_ags_encounters(
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
    encounter_guid = group_sighting.json['config']['sighting']['encounters'][0]['guid']
    assert encounter_guid

    # patch time value on encounter
    encounter_path = f'{asset_group_sighting_guid}/encounter/{encounter_guid}'
    time_value = '2000-01-01T01:01:01+00:00'
    patch_time = [
        utils.patch_add_op('time', time_value),
        utils.patch_add_op('timeSpecificity', 'month'),
    ]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        patch_time,
    )

    # now verify change
    group_sighting_verify = asset_group_utils.read_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
    )
    assert (
        group_sighting_verify.json['config']['sighting']['encounters'][0]['time']
        == time_value
    )
    assert (
        group_sighting_verify.json['config']['sighting']['encounters'][0][
            'timeSpecificity'
        ]
        == 'month'
    )

    # patch in a few encounter fields
    locality = '42'
    taxonomy = str(uuid.uuid4())
    new_time_value = '2020-01-01T01:01:01+00:00'
    patch_enc_data = [
        utils.patch_add_op('verbatimLocality', locality),
        utils.patch_add_op('time', new_time_value),
        utils.patch_add_op('taxonomy', taxonomy),
    ]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        encounter_path,
        patch_enc_data,
    )

    group_sighting_verify = asset_group_utils.read_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
    ).json
    gas = asset_group_utils.read_asset_group_sighting_as_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid,
    ).json
    ags_enc = group_sighting_verify['config']['sighting']['encounters'][0]
    ags_as_sighting_enc = gas['encounters'][0]
    assert ags_enc['verbatimLocality'] == locality
    assert ags_enc['taxonomy'] == taxonomy
    assert ags_as_sighting_enc['verbatimLocality'] == locality
    assert ags_as_sighting_enc['taxonomy'] == taxonomy


# moving annot from one encounter to the other
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_asset_group_annots(
    flask_app_client, researcher_1, regular_user, test_root, db, empty_individual, request
):
    # pylint: disable=invalid-name

    def get_encounter_path(ags_guid, encounter_guid):
        return f'{ags_guid}/encounter/{encounter_guid}'

    def create_and_add_annot(ags_data, asset_num, encounter_num):
        annot_resp = annot_utils.create_annotation_simple(
            flask_app_client,
            researcher_1,
            ags_data['assets'][asset_num]['guid'],
        ).json
        annotation_guid = annot_resp['guid']

        # Add annot, should succeed
        annot_add_resp = asset_group_utils.patch_asset_group_sighting(
            flask_app_client,
            researcher_1,
            get_encounter_path(
                ags_data['guid'], ags_data['encounters'][encounter_num]['guid']
            ),
            [utils.patch_add_op('annotations', annotation_guid)],
        ).json

        enc_annots = annot_add_resp['config']['sighting']['encounters'][encounter_num][
            'annotations'
        ]

        assert annotation_guid in enc_annots
        return annotation_guid

    # Using bulk creation data means we get an AGS with two encounters which is what we need to add the annot to
    # the first one and then move it to the second
    data = asset_group_utils.get_bulk_creation_data(test_root, request)
    group_resp = asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get()
    ).json
    asset_group_uuid = group_resp['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_uuid
        )
    )

    ags1 = asset_group_utils.extract_ags_data(group_resp, 0)
    assert len(ags1['encounters']) == 2

    annotation1_guid = create_and_add_annot(ags1, asset_num=0, encounter_num=0)

    # Add annot to enc 2, should remove it from enc 1
    annot_add_resp = asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        get_encounter_path(ags1['guid'], ags1['encounters'][1]['guid']),
        [utils.patch_add_op('annotations', annotation1_guid)],
    ).json

    enc1_annots = annot_add_resp['config']['sighting']['encounters'][0]['annotations']
    enc2_annots = annot_add_resp['config']['sighting']['encounters'][1]['annotations']
    assert len(enc1_annots) == 0
    assert len(enc2_annots) == 1
    assert enc2_annots[0] == annotation1_guid

    # Add second annot, should succeed
    annotation2_guid = create_and_add_annot(ags1, asset_num=0, encounter_num=1)

    # Try forbidden operation
    ags2 = asset_group_utils.extract_ags_data(group_resp, 1)
    assert len(ags2['encounters']) == 2
    # Add annot2 to enc 1 in ags 2, should fail
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        get_encounter_path(ags2['guid'], ags2['encounters'][0]['guid']),
        [utils.patch_add_op('annotations', annotation2_guid)],
        400,
        f"Encounter {ags2['encounters'][0]['guid']} Asset cannot be in multiple sightings",
    )


# tweaking the asset references in the sighting
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_asset_group_assets(
    flask_app_client, researcher_1, regular_user, test_root, db, empty_individual, request
):
    # pylint: disable=invalid-name

    # Using bulk creation data means we get an AGS with two encounters which is what we need be able to shuffle
    # assets around
    data = asset_group_utils.get_bulk_creation_data(test_root, request)
    group_resp = asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get()
    ).json
    asset_group_uuid = group_resp['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_uuid
        )
    )

    ags1 = asset_group_utils.extract_ags_data(group_resp, 0)
    ags2 = asset_group_utils.extract_ags_data(group_resp, 1)
    assert len(ags1['assets']) == 2
    assert len(ags2['assets']) == 2

    # add a non existent file
    expected_resp = f'absent_file.jpg not in Group for assetGroupSighting {ags1["guid"]}'
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        ags1['guid'],
        [{'op': 'add', 'path': '/assetReferences', 'value': 'absent_file.jpg'}],
        400,
        expected_resp,
    )

    expected_resp = f"{ags2['assets'][0]['filename']} already in assetGroupSighting {ags2['guid']}, remove from this first."
    # Add file that's in a different AGS
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        ags1['guid'],
        [
            {
                'op': 'add',
                'path': '/assetReferences',
                'value': ags2['assets'][0]['filename'],
            }
        ],
        400,
        expected_resp,
    )

    # remove valid one
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        ags2['guid'],
        [
            {
                'op': 'remove',
                'path': '/assetReferences',
                'value': ags2['assets'][0]['filename'],
            }
        ],
    )

    # remove one that wasn't there anyway
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        ags2['guid'],
        [
            {
                'op': 'remove',
                'path': '/assetReferences',
                'value': ags1['assets'][0]['filename'],
            }
        ],
    )

    # Add removed one back
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        ags2['guid'],
        [
            {
                'op': 'add',
                'path': '/assetReferences',
                'value': ags2['assets'][0]['filename'],
            }
        ],
    )
