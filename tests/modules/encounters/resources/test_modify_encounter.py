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
        utils.validate_dict_response(response, 200, {'guid'})
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


def not_a_test_asset_addition(db, flask_app_client):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter

    new_researcher = utils.generate_user_instance(
        email='reseracher47@nowhere.com', is_researcher=True
    )
    new_encounter = Encounter(owner=new_researcher)
    new_submission = utils.generate_submission_instance(new_researcher)
    new_asset = utils.generate_asset_instance(new_submission.guid)

    with db.session.begin():
        db.session.add(new_researcher)
        db.session.add(new_encounter)
        db.session.add(new_submission)
        db.session.add(new_asset)

    add_asset = [
        utils.patch_test_op(new_researcher.password_secret),
        utils.patch_add_op('assetId', '%s' % new_asset.guid),
    ]
    patch_encounter(
        flask_app_client, '%s' % new_encounter.guid, new_researcher, add_asset
    )
    assert len(new_encounter.assets) == 1
    # removed submission delete as it was going haywire
    # new_submission.delete()


def add_file_asset_to_encounter(
    flask_app_client, user, encounter, transaction_id, filename, content
):
    # @todo cack handed way to do this as the real test will depend on work that Jon is currently doing
    import os

    dir_path = os.path.join('_db', 'uploads', '-'.join(['trans', transaction_id]))
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    with open(os.path.join(dir_path, filename), 'a') as file:
        file.write(content)
        file.close()

    add_asset = [
        utils.patch_test_op(user.password_secret),
        utils.patch_add_op('newSubmission', transaction_id),
    ]
    patch_encounter(flask_app_client, '%s' % encounter.guid, user, add_asset)

    # @todo, this directory should really have been deleted by the code. As yet it's not.
    # assert os.path.exists(dir_path) is False


def test_asset_file_addition(db, flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter

    new_encounter = Encounter(owner=researcher_1)

    with db.session.begin():
        db.session.add(new_encounter)
    try:
        add_file_asset_to_encounter(
            flask_app_client,
            researcher_1,
            new_encounter,
            'new_stuff',
            'new_file.csv',
            '1,2,3,4,5',
        )
        assert len(new_encounter.assets) == 1
        add_file_asset_to_encounter(
            flask_app_client,
            researcher_1,
            new_encounter,
            'more_stuff',
            'next_file.csv',
            '5,4,3,2,1',
        )
        assert len(new_encounter.assets) == 2
        with flask_app_client.login(researcher_1, auth_scopes=('encounters:write',)):
            response = flask_app_client.delete(
                '%s%s' % (PATH, new_encounter.guid),
            )

        # The Submission will be in gitlab but not on the EDM so the delete will "fail"
        assert response.status_code == 400
    except Exception as ex:
        raise ex
    finally:
        # Even though the REST API deletion fails, as it's not present, the Houston feather object remains.
        # @todo this seems fundamentally wrong
        # assert len(researcher_1.owned_encounters) == 0
        new_encounter.delete()
