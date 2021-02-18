# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.encounters.resources import utils as enc_utils


#def test_create_and_delete_project(flask_app_client, anonymous_user_login):   researcher_1
def test_create_and_delete_encounter(flask_app_client, regular_user, admin_user):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter

    response = enc_utils.create_encounter(
        flask_app_client, regular_user
    )
    assert response.status_code == 200
    enc_guid = response.json['result']['guid']

    # note this is only feather object, but enough just to test owner
    read_enc = Encounter.query.get(enc_guid)
    assert read_enc.owner == regular_user

    # Try reading it back
    response = enc_utils.read_encounter(flask_app_client, regular_user, enc_guid)
    assert response.status_code == 200
    assert response.json['id'] == str(enc_guid)
    assert response.json['locationId'] == 'PYTEST'

    # And deleting it
    #enc_utils.delete_encounter(flask_app_client, admin_user, enc_guid)

    #read_enc = Encounter.query.get(enc_guid)
    #assert read_enc is None
