# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_res_utils
from tests.modules.individuals import utils as individual_utils
from app.modules.individuals.models import Individual
import pytest
from tests import utils as test_utils
import logging

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_basics(db, flask_app_client, researcher_1, request):
    sighting1, encounter1 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_1
    )
    request.addfinalizer(sighting1.delete_cascade)
    individual1_id = str(encounter1.individual_guid)
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_1, individual1_id
        )
    )
    sighting2, encounter2 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_1
    )
    request.addfinalizer(sighting2.delete_cascade)
    individual2_id = str(encounter2.individual_guid)

    data_in = {}  # first try with bunk data
    response = individual_res_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        individual1_id,
        data_in,
        expected_status_code=500,
    )
    assert 'message' in response and 'list of individuals' in response['message']

    # send an invalid guid
    bad_id = '00000000-0000-0000-0000-000000002170'
    data_in = [bad_id]
    response = individual_res_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        individual1_id,
        data_in,
        expected_status_code=500,
    )
    assert 'message' in response and f'{bad_id} is invalid' in response['message']

    # now with valid list of from-individuals
    data_in = {
        'fromIndividualIds': [individual2_id],
    }
    # data_in = [individual2_id]  # would also be valid
    # note: this tests positive permission case as well (user owns everything)
    response = individual_res_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        individual1_id,
        data_in,
    )
    individual2 = Individual.query.get(individual2_id)
    assert not individual2


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_permissions(
    db, flask_app_client, researcher_1, researcher_2, contributor_1, request
):
    sighting1, encounter1 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_1
    )
    request.addfinalizer(sighting1.delete_cascade)
    individual1_id = str(encounter1.individual_guid)
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_1, individual1_id
        )
    )
    sighting2, encounter2 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_2
    )
    request.addfinalizer(sighting2.delete_cascade)
    individual2_id = str(encounter2.individual_guid)
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_2, individual2_id
        )
    )

    # this tests as researcher_2, which should trigger a merge-request (owns just 1 encounter)
    data_in = [individual2_id]
    response = individual_res_utils.merge_individuals(
        flask_app_client,
        researcher_2,
        individual1_id,
        data_in,
        expected_fields={
            'merge_request',
            'request_id',
            'deadline',
            'blocking_encounters',
        },
    )
    assert response['merge_request']
    assert response['blocking_encounters'] == [str(encounter1.guid)]
    # check that the celery task is there and contains what it should
    assert response['request_id']
    try:
        req_data = Individual.get_merge_request_data(response['request_id'])
        assert req_data
        assert req_data['request']['args'][0] == individual1_id
    except NotImplementedError:
        log.info('Merge-request test skipped; no celery workers available')

    # a user who owns none (403 fail, no go)
    response = individual_res_utils.merge_individuals(
        flask_app_client,
        contributor_1,
        individual1_id,
        data_in,
        expected_status_code=403,
    )

    # anonymous (401)
    response = individual_res_utils.merge_individuals(
        flask_app_client,
        None,
        individual1_id,
        data_in,
        expected_status_code=401,
    )


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_get_data_and_voting(
    db, flask_app_client, researcher_1, researcher_2, contributor_1, request
):
    bad_id = '00000000-0000-0000-0000-000000002170'
    # first anon permission check (401)
    response = individual_res_utils.get_or_vote_individuals(
        flask_app_client,
        None,
        bad_id,
        expected_status_code=401,
    )

    # first lets see if we have celery running, cuz things go south if we do not
    try:
        data = Individual.get_merge_request_data(bad_id)
        assert not data
    except NotImplementedError:
        pytest.skip('celery not running')

    # invalid id (404)
    response = individual_res_utils.get_or_vote_individuals(
        flask_app_client,
        contributor_1,  # just needs to not be anon
        bad_id,
        expected_status_code=404,
    )

    # now we need real data
    sighting1, encounter1 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_1
    )
    request.addfinalizer(sighting1.delete_cascade)
    individual1_id = str(encounter1.individual_guid)
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_1, individual1_id
        )
    )
    sighting2, encounter2 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_2
    )
    request.addfinalizer(sighting2.delete_cascade)
    individual2_id = str(encounter2.individual_guid)
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_2, individual2_id
        )
    )

    # this tests as researcher_2, which should trigger a merge-request (owns just 1 encounter)
    data_in = [individual2_id]
    response = individual_res_utils.merge_individuals(
        flask_app_client,
        researcher_2,
        individual1_id,
        data_in,
        expected_fields={
            'merge_request',
            'request_id',
            'deadline',
            'blocking_encounters',
        },
    )
    assert response['merge_request']
    assert response['blocking_encounters'] == [str(encounter1.guid)]
    request_id = response.get('request_id')
    assert request_id
    # we should have a valid merge request now to test against

    # so now we test unauthorized user (403)
    response = individual_res_utils.get_or_vote_individuals(
        flask_app_client,
        contributor_1,
        request_id,
        expected_status_code=403,
    )

    # now this get-data should work
    response = individual_res_utils.get_or_vote_individuals(
        flask_app_client,
        researcher_1,
        request_id,
    )
    assert response.json
    assert 'request' in response.json
    assert response.json['request'].get('id') == request_id

    # invalid vote (422)
    response = individual_res_utils.get_or_vote_individuals(
        flask_app_client,
        researcher_1,
        request_id,
        'fubar',
        expected_status_code=422,
    )

    # valid vote
    response = individual_res_utils.get_or_vote_individuals(
        flask_app_client,
        researcher_1,
        request_id,
        'allow',
    )
    assert response.json
    assert response.json.get('vote') == 'allow'
