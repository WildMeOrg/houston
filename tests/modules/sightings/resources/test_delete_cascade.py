# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

# purpose of this is to really try to cover all permutations of the edm delete-cascade scenarios.  DEX-595
#
# there are a couple cases already covered:
#
# - tests/modules/encounters/resources/test_delete_encounter.py::test_delete_method
#   this checks direct "DELETE encounter-guid" api, when enc-delete takes a sighting *and* indvidiual with it
#
# - tests/modules/sightings/resources/test_create_sighting.py::test_create_and_modify_and_delete_sighting
#   checks PATCH on sighting path=/encounters op=remove, but only checks sighting-delete-cascade
#
# but there may be some redundancy with these tests in here.


from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.encounters.resources import utils as encounter_utils
from tests import utils as test_utils
import datetime
import pytest

from tests.utils import module_unavailable

timestamp = datetime.datetime.now().isoformat() + '+00:00'


# this one will do nothing with individuals
@pytest.mark.skipif(
    module_unavailable('sightings', 'encounters'), reason='Sightings module disabled'
)
def test_sighting_cascade(flask_app_client, test_root, researcher_1, request, db):
    from app.modules.sightings.models import Sighting

    orig_ct = test_utils.all_count(db)
    data_in = {
        'encounters': [{}, {}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': 'test',
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

    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting'] + 1
    assert ct['Encounter'] == orig_ct['Encounter'] + 2

    # okay cuz we are left with a single encounter still
    response = encounter_utils.delete_encounter(flask_app_client, researcher_1, enc0_id)
    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting'] + 1
    assert ct['Encounter'] == orig_ct['Encounter'] + 1

    # this should fail, as its final encounter
    response = encounter_utils.delete_encounter(
        flask_app_client, researcher_1, enc1_id, expected_status_code=400
    )

    # now it should work, taking the sighting with it
    headers = (('x-allow-delete-cascade-sighting', True),)
    response = encounter_utils.delete_encounter(
        flask_app_client, researcher_1, enc1_id, headers=headers
    )
    # this is reported by edm, which sighting got cascade-deleted
    assert response.headers.get('x-deletedSighting-guid') == sighting_id
    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting']
    assert ct['Encounter'] == orig_ct['Encounter']


# this one only tests individuals
@pytest.mark.skipif(
    module_unavailable('sightings', 'encounters'), reason='Sightings module disabled'
)
def test_individual_cascade(flask_app_client, test_root, researcher_1, request, db):
    orig_ct = test_utils.all_count(db)
    data_in = {
        'encounters': [{}, {}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': 'test',
    }
    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=data_in,
    )
    assert len(uuids['encounters']) == 2
    sighting_id = uuids['sighting']
    encounter1_id = uuids['encounters'][0]
    encounter2_id = uuids['encounters'][1]
    individual_id = uuids['individual']
    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting'] + 1
    assert ct['Encounter'] == orig_ct['Encounter'] + 2
    assert ct['Individual'] == orig_ct['Individual'] + 1

    # note only encounter1 has individual on it, so this should trigger cascade
    response = encounter_utils.delete_encounter(
        flask_app_client, researcher_1, encounter1_id, expected_status_code=400
    )

    # now it should be okay
    headers = (('x-allow-delete-cascade-individual', True),)
    response = encounter_utils.delete_encounter(
        flask_app_client, researcher_1, encounter1_id, headers=headers
    )
    # this is reported by edm, which individuals got cascade-deleted
    assert response.headers.get('x-deletedIndividual-guids') == individual_id
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 1
    assert ct['Individual'] == orig_ct['Individual']

    # now we add an individual to encounter2
    individual_data_in = {
        'encounters': [{'id': str(encounter2_id)}],
    }
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    assert individual_response.json['result']['id'] is not None
    individual_id = individual_response.json['result']['id']
    ct = test_utils.all_count(db)
    assert ct['Encounter'] == orig_ct['Encounter'] + 1
    assert ct['Individual'] == orig_ct['Individual'] + 1

    # this will allow cascade delete of individual and sighting
    headers = (
        ('x-allow-delete-cascade-sighting', True),
        ('x-allow-delete-cascade-individual', True),
    )
    response = encounter_utils.delete_encounter(
        flask_app_client, researcher_1, encounter2_id, headers=headers
    )
    assert response.headers.get('x-deletedSighting-guid') == sighting_id
    assert response.headers.get('x-deletedIndividual-guids') == individual_id
    # should bring us back to where we started
    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting']
    assert ct['Encounter'] == orig_ct['Encounter']
    assert ct['Individual'] == orig_ct['Individual']


# this tests deleting a sighting which contains encounters which have individuals
@pytest.mark.skipif(
    module_unavailable('sightings', 'encounters'), reason='Sightings module disabled'
)
def test_multi_cascade(flask_app_client, test_root, researcher_1, request, db):
    orig_ct = test_utils.all_count(db)
    data_in = {
        'encounters': [{}, {}],
        'time': timestamp,
        'timeSpecificity': 'time',
        'locationId': 'test',
    }
    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=data_in,
    )
    assert len(uuids['encounters']) == 2
    sighting_id = uuids['sighting']
    # encounter1_id = uuids['encounters'][0]
    encounter2_id = uuids['encounters'][1]
    individual1_id = uuids['individual']
    ct = test_utils.all_count(db)
    assert ct['Sighting'] == orig_ct['Sighting'] + 1
    assert ct['Encounter'] == orig_ct['Encounter'] + 2
    assert ct['Individual'] == orig_ct['Individual'] + 1

    # note only encounter1 has individual on it, so add one to encounter2
    individual_data_in = {
        'encounters': [{'id': str(encounter2_id)}],
    }
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    assert individual_response.json['result']['id'] is not None
    individual2_id = individual_response.json['result']['id']
    ct = test_utils.all_count(db)
    assert ct['Individual'] == orig_ct['Individual'] + 2

    response = sighting_utils.delete_sighting(
        flask_app_client, researcher_1, sighting_id, expected_status_code=400
    )

    # lets say we are okay - should delete *two* individuals
    headers = (('x-allow-delete-cascade-individual', True),)
    response = sighting_utils.delete_sighting(
        flask_app_client, researcher_1, sighting_id, headers=headers
    )
    assert response
    assert response.headers
    del_indiv_header = response.headers.get('x-deletedIndividual-guids')
    assert del_indiv_header == ', '.join(
        [individual1_id, individual2_id]
    ) or del_indiv_header == ', '.join([individual2_id, individual1_id])
    ct = test_utils.all_count(db)
    assert ct['Individual'] == orig_ct['Individual']
