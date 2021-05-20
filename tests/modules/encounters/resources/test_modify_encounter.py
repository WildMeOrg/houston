# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json
from tests import utils


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
        utils.validate_dict_response(response, 200, {'success', 'result'})
    else:
        utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def test_modify_encounter(db, flask_app_client, researcher_1, researcher_2):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter

    new_encounter_1 = Encounter(owner=researcher_1)

    with db.session.begin():
        db.session.add(new_encounter_1)

    # non Owner cannot make themselves the owner
    new_owner_as_res_2 = [
        utils.patch_test_op(researcher_2.password_secret),
        utils.patch_replace_op('owner', '%s' % researcher_2.guid),
    ]

    patch_encounter(
        flask_app_client,
        '%s' % new_encounter_1.guid,
        researcher_2,
        new_owner_as_res_2,
        403,
    )
    assert new_encounter_1.owner == researcher_1

    # But the owner can
    new_owner_as_res_1 = [
        utils.patch_test_op(researcher_1.password_secret),
        utils.patch_replace_op('owner', '%s' % researcher_2.guid),
    ]
    patch_encounter(
        flask_app_client, '%s' % new_encounter_1.guid, researcher_1, new_owner_as_res_1
    )
    assert new_encounter_1.owner == researcher_2

    # test changing locationID via patch
    new_val = 'LOCATION_TEST_VALUE'
    patch_data = [utils.patch_replace_op('locationID', new_val)]
    res = patch_encounter(
        flask_app_client, '%s' % new_encounter_1.guid, researcher_1, patch_data
    )
    print(f'(<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<{res})')
    assert res is None
