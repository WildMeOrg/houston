# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from unittest import mock

from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.extensions.edm import utils as edm_utils


def test_modify_encounter(
    db, flask_app_client, researcher_1, researcher_2, admin_user, test_asset_group_uuid
):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    first_enc_guid = response.json['result']['encounters'][0]['id']
    assert first_enc_guid is not None
    new_encounter_1 = Encounter.query.get(first_enc_guid)

    # test that we cant mix edm/houston
    patch_data = [
        utils.patch_replace_op('owner', str(researcher_1.guid)),
        utils.patch_replace_op('locationId', 'FAIL'),
    ]
    res = enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_1,
        patch_data,
        400,
    )

    # non Owner cannot make themselves the owner
    new_owner_as_res_2 = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_replace_op('owner', str(researcher_2.guid)),
    ]

    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_2,
        new_owner_as_res_2,
        403,
    )
    assert new_encounter_1.owner == researcher_1

    # But the owner can
    new_owner_as_res_1 = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_replace_op('owner', str(researcher_2.guid)),
    ]
    enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_1, new_owner_as_res_1
    )
    assert new_encounter_1.owner == researcher_2

    # test changing locationId via patch
    new_val = 'LOCATION_TEST_VALUE'
    patch_data = [utils.patch_replace_op('locationId', new_val)]
    res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )
    assert res.json['id'] == str(new_encounter_1.guid)

    # Attach some assets and annotations
    from app.modules.asset_groups.models import AssetGroup

    assets = AssetGroup.query.get(test_asset_group_uuid).assets
    new_encounter_1.sighting.add_assets(assets)
    for asset in assets:
        annot_utils.create_annotation(
            flask_app_client, researcher_2, str(asset.guid), str(new_encounter_1.guid)
        )

    annotations = [
        {
            'asset_guid': str(ann.asset.guid),
            'ia_class': 'test',
            'guid': str(ann.guid),
        }
        for ann in new_encounter_1.annotations
    ]

    enc = enc_utils.read_encounter(flask_app_client, researcher_2, new_encounter_1.guid)
    assert enc.json == {
        'customFields': {},
        'id': str(new_encounter_1.guid),
        'guid': str(new_encounter_1.guid),
        'locationId': new_val,
        'timeValues': [None, None, None, 0, 0],
        'version': new_encounter_1.version,
        'createdHouston': new_encounter_1.created.isoformat() + '+00:00',
        'updatedHouston': new_encounter_1.updated.isoformat() + '+00:00',
        'owner': {
            'full_name': researcher_2.full_name,
            'guid': str(researcher_2.guid),
            'profile_fileupload': None,
        },
        'submitter': {
            'full_name': researcher_1.full_name,
            'guid': str(researcher_1.guid),
            'profile_fileupload': None,
        },
        'annotations': annotations,
        'hasEdit': True,
        'hasView': True,
    }

    # now we test modifying customFields
    cfd_id = edm_utils.custom_field_create(
        flask_app_client, admin_user, 'test_cfd', cls='Encounter'
    )
    assert cfd_id is not None

    # test patch on customFields
    new_cfd_test_value = 'NEW_CFD_TEST_VALUE'
    patch_data = [
        utils.patch_replace_op(
            'customFields', {'id': cfd_id, 'value': new_cfd_test_value}
        )
    ]
    response = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )

    assert response.status_code == 200
    assert response.json['id'] == str(new_encounter_1.guid)
    # check that change was made
    enc = enc_utils.read_encounter(flask_app_client, researcher_2, new_encounter_1.guid)
    assert enc.json['id'] == str(new_encounter_1.guid)
    # make sure customFields value has been altered
    assert 'customFields' in enc.json
    assert cfd_id in enc.json['customFields']
    assert enc.json['customFields'][cfd_id] == new_cfd_test_value

    new_encounter_1.sighting.delete_cascade()
    new_encounter_1.delete()


def test_modify_encounter_error(flask_app, flask_app_client, researcher_1):
    from app.modules.encounters.models import Encounter

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    first_enc_guid = response.json['result']['encounters'][0]['id']

    def edm_return_500(*args, **kwargs):
        response = mock.Mock(ok=False, status_code=500)
        response.json.return_value = None
        return response

    # test edm returning 500 error
    new_val = 'LOCATION_TEST_VALUE'
    patch_data = [utils.patch_replace_op('locationId', new_val)]
    with mock.patch.object(
        flask_app.edm, 'request_passthrough', side_effect=edm_return_500
    ):
        res = enc_utils.patch_encounter(
            flask_app_client,
            first_enc_guid,
            researcher_1,
            patch_data,
            expected_status_code=500,
        )
    assert res.json['status'] == 500

    Encounter.query.get(first_enc_guid).sighting.delete()
    Encounter.query.get(first_enc_guid).delete()
