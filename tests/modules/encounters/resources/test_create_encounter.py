# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.encounters.resources import utils as enc_utils


# def test_create_and_delete_project(flask_app_client, anonymous_user_login):   researcher_1
def test_create_and_delete_encounter(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter

    response = enc_utils.create_encounter(flask_app_client, researcher_1)
    enc_guid = response.json['result']['guid']

    # note this is only feather object, but enough just to test owner
    read_enc = Encounter.query.get(enc_guid)
    assert read_enc.owner == researcher_1

    # Try reading it back
    response = enc_utils.read_encounter(flask_app_client, researcher_1, enc_guid)
    assert response.json['locationId'] == 'PYTEST'

    # And deleting it
    enc_utils.delete_encounter(flask_app_client, researcher_1, enc_guid)

    read_enc = Encounter.query.get(enc_guid)
    assert read_enc is None


def test_create_and_delete_encounter_anonymous(
    flask_app_client, researcher_1, staff_user
):
    from app.modules.encounters.models import Encounter

    response = enc_utils.create_encounter(flask_app_client, None)
    enc_guid = response.json['result']['guid']

    # note this is only feather object, but enough just to test owner
    from app.modules.users.models import User

    read_enc = Encounter.query.get(enc_guid)
    assert read_enc.owner is User.get_public_user()

    # Try reading it back
    response = enc_utils.read_encounter(flask_app_client, researcher_1, enc_guid)
    assert response.json['locationId'] == 'PYTEST'

    # And deleting it
    enc_utils.delete_encounter(flask_app_client, staff_user, enc_guid)

    read_enc = Encounter.query.get(enc_guid)
    assert read_enc is None
