# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

from tests import utils as test_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.modules.individuals.resources import utils as indiv_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_delete_method(
    db, flask_app_client, researcher_1, test_root, staff_user, request
):
    from app.modules.sightings.models import Sighting

    # we should end up with these same counts (which _should be_ all zeros!)
    orig_ct = test_utils.all_count(db)

    data_in = {
        'time': test_utils.isoformat_timestamp_now(),
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
        'encounters': [
            {},
            {'locationId': test_utils.get_valid_location_id()},
        ],
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )

    sighting_id = uuids['sighting']
    sighting = Sighting.query.get(sighting_id)
    assert sighting is not None
    assert len(uuids['encounters']) == 2
    enc0_id = uuids['encounters'][0]
    enc1_id = uuids['encounters'][1]
    assert enc0_id is not None
    assert enc1_id is not None

    # assign indiv to both encounters to test cascade-delete of individual as well
    indiv_enc_json = {'encounters': [{'id': enc0_id}, {'id': enc1_id}]}
    response = indiv_utils.create_individual(
        flask_app_client,
        staff_user,
        data_in=indiv_enc_json,
    )
    individual_guid = response.json['guid']
    assert individual_guid is not None

    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting'] + 1  # one more sighting
    assert ct['Encounter'] == orig_ct['Encounter'] + 2  # two more encounters
    assert ct['Individual'] == orig_ct['Individual'] + 1  # one more individual

    # this should be ok, cuz one enc remains (no cascade effects)
    enc_utils.delete_encounter(flask_app_client, staff_user, enc0_id)
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 1
    assert (
        ct['Individual'] == orig_ct['Individual'] + 1
    )  # just to confirm indiv is still there

    # test that sighting is correct, with single encounter remaining
    get_resp = sighting_utils.read_sighting(flask_app_client, researcher_1, sighting_id)
    assert len(get_resp.json['encounters']) == 1

    # but this should then fail, cuz its the last enc and will take the sighting with it
    response = enc_utils.delete_encounter(
        flask_app_client, staff_user, enc1_id, expected_status_code=400
    )
    assert response.json['vulnerableSightingGuid'] == sighting_id
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 1

    # this will fail cuz it *only* allows sighting-cascade and we need individual also
    headers = (('x-allow-delete-cascade-sighting', True),)
    response = enc_utils.delete_encounter(
        flask_app_client, staff_user, enc1_id, headers=headers, expected_status_code=400
    )
    assert response.json['vulnerableIndividualGuid'] == individual_guid

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
    assert ct['Sighting'] == orig_ct['Sighting']
    assert ct['Encounter'] == orig_ct['Encounter']
    assert ct['Individual'] == orig_ct['Individual']
