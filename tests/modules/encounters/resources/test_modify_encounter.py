# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json
from tests import utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.extensions.edm import utils as edm_utils


PATH = '/api/v1/encounters/'


def patch_encounter(
    flask_app_client, encounter_guid, user, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('encounters:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, encounter_guid),
            content_type='application/json',
            data=json.dumps(data),
        )
    if expected_status_code == 200:
        utils.validate_dict_response(response, 200, {'id', 'version'})
    else:
        utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def test_modify_encounter(db, flask_app_client, researcher_1, researcher_2, admin_user):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    first_enc_guid = response.json['result']['encounters'][0]['id']
    assert first_enc_guid is not None
    new_encounter_1 = Encounter.query.get(first_enc_guid)

    # non Owner cannot make themselves the owner
    new_owner_as_res_2 = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_replace_op('owner', str(researcher_2.guid)),
    ]

    patch_encounter(
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
    patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_1, new_owner_as_res_1
    )
    assert new_encounter_1.owner == researcher_2

    # test changing locationId via patch
    new_val = 'LOCATION_TEST_VALUE'
    patch_data = [utils.patch_replace_op('locationId', new_val)]
    res = patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )
    assert res is not None
    assert res.status_code == 200
    assert res.json['id'] == str(new_encounter_1.guid)

    enc = enc_utils.read_encounter(flask_app_client, researcher_2, new_encounter_1.guid)
    assert enc.json['id'] == str(new_encounter_1.guid)
    assert enc.json['locationId'] == new_val

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
    response = patch_encounter(
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
