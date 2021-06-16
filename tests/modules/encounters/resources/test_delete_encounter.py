# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.modules.individuals.resources import utils as indiv_utils
from tests import utils as test_utils
import datetime

timestamp = datetime.datetime.now().isoformat() + 'Z'


def test_delete_method(db, flask_app_client, researcher_1, test_root, staff_user):
    from app.modules.sightings.models import Sighting

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = test_utils.all_count(db)

    data_in = {
        'startTime': timestamp,
        'locationId': 'test_delete_method',
        'encounters': [
            {},
            {'locationId': 'test2'},
        ],
    }
    response = sighting_utils.create_sighting(
        flask_app_client, researcher_1, expected_status_code=200, data_in=data_in
    )
    assert response.json['success']

    sighting_id = response.json['result']['id']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None

    enc0_id = response.json['result']['encounters'][0]['id']
    enc1_id = response.json['result']['encounters'][1]['id']
    assert enc0_id is not None
    assert enc1_id is not None

    # assign indiv to both encounters to test cascade-delete of individual as well
    indiv_enc_json = {'encounters': [{'id': enc0_id}, {'id': enc1_id}]}
    response = indiv_utils.create_individual(
        flask_app_client,
        staff_user,
        data_in=indiv_enc_json,
    )
    individual_guid = response.json['result']['id']
    assert individual_guid is not None

    ct = test_utils.all_count(db)
    assert ct[0] == orig_ct[0] + 1  # one more sighting
    assert ct[1] == orig_ct[1] + 2  # two more encounters
    assert ct[4] == orig_ct[4] + 1  # one more individual

    # this should be ok, cuz one enc remains (no cascade effects)
    enc_utils.delete_encounter(flask_app_client, staff_user, enc0_id)
    ct = test_utils.all_count(db)
    assert ct[1] == orig_ct[1] + 1
    assert ct[4] == orig_ct[4] + 1  # just to confirm indiv is still there

    # but this should then fail, cuz its the last enc and will take the sighting with it
    response = enc_utils.delete_encounter(
        flask_app_client, staff_user, enc1_id, expected_status_code=400
    )
    ct = test_utils.all_count(db)
    assert ct[1] == orig_ct[1] + 1
    assert response.json['edm_status_code'] == 604

    # this will fail cuz it *only* allows sighting-cascade and we need individual also
    headers = (('x-allow-delete-cascade-sighting', True),)
    response = enc_utils.delete_encounter(
        flask_app_client, staff_user, enc1_id, headers=headers, expected_status_code=400
    )
    assert response.json['edm_status_code'] == 605

    # now this should work but take the sighting and individual with it as well
    headers = (
        ('x-allow-delete-cascade-individual', True),
        ('x-allow-delete-cascade-sighting', True),
    )
    response = enc_utils.delete_encounter(
        flask_app_client, staff_user, enc1_id, headers=headers
    )
    assert (
        response.headers['x-deletedSighting-guid'] == sighting_id
    )  # header tells us sighting cascade-deleted
    ct = test_utils.all_count(db)  # back where we started
    assert ct[0] == orig_ct[0]
    assert ct[1] == orig_ct[1]
    assert ct[4] == orig_ct[4]
