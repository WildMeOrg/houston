# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from app.modules.individuals.models import Individual
import pytest
import json
from tests import utils as test_utils

increment = 0


def prep_data(db, flask_app_client, user, individual_sex='female'):
    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    global increment
    sighting_data_in = {
        'encounters': [
            {
                'decimalLatitude': 45.999,
                'decimalLongitude': 45.999,
                'verbatimLocality': 'Legoland Town Square',
                'locationId': f'Location {increment}',
            }
        ],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': f'test-{increment}',
    }
    individual_data_in = {
        'names': {'defaultName': f'NAME {increment}'},
        'sex': individual_sex,
        'comments': 'Test Individual',
        'timeOfBirth': '872846040000',
    }
    increment += 1
    res_sighting, res_individual = sighting_utils.create_sighting_and_individual(
        flask_app_client, user, sighting_data_in, individual_data_in
    )
    json_sighting = res_sighting.json['result']
    json_individual = res_individual.json['result']
    assert json_sighting['encounters'][0]['id'] == json_individual['encounters'][0]['id']
    encounter = Encounter.query.get(json_sighting['encounters'][0]['id'])
    assert encounter is not None
    sighting = Sighting.query.get(json_sighting['id'])
    assert sighting is not None
    return sighting, encounter


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_basics(db, flask_app_client, researcher_1):
    individual1_id = None
    sighting1 = None
    encounter1 = None
    individual2_id = None
    sighting2 = None
    encounter2 = None
    try:
        sighting1, encounter1 = prep_data(db, flask_app_client, researcher_1)
        individual1_id = str(encounter1.individual_guid)
        sighting2, encounter2 = prep_data(db, flask_app_client, researcher_1)
        individual2_id = str(encounter2.individual_guid)

        data_in = {}  # first try with bunk data
        response = test_utils.post_via_flask(
            flask_app_client,
            researcher_1,
            scopes=('individuals:write',),
            path=f'/api/v1/individuals/{individual1_id}/merge',
            data=data_in,
            expected_status_code=500,
            response_200={'success'},
        )
        assert (
            'message' in response.json
            and 'list of individuals' in response.json['message']
        )

        # send an invalid guid
        bad_id = '00000000-0000-0000-0000-000000002170'
        data_in = [bad_id]
        response = test_utils.post_via_flask(
            flask_app_client,
            researcher_1,
            scopes=('individuals:write',),
            path=f'/api/v1/individuals/{individual1_id}/merge',
            data=data_in,
            expected_status_code=500,
            response_200={'success'},
        )
        assert (
            'message' in response.json
            and f'{bad_id} is invalid' in response.json['message']
        )

        # now with valid list of from-individuals
        data_in = {
            'fromIndividualIds': [individual2_id],
        }
        # data_in = [individual2_id]  # would also be valid
        # note: this tests positive permission case as well (user owns everything)
        response = test_utils.post_via_flask(
            flask_app_client,
            researcher_1,
            scopes=('individuals:write',),
            path=f'/api/v1/individuals/{individual1_id}/merge',
            data=data_in,
            expected_status_code=200,
            response_200={'merged'},
        )
        individual2 = Individual.query.get(individual2_id)
        assert not individual2

    finally:
        individual_utils.delete_individual(flask_app_client, researcher_1, individual1_id)
        # individual2 is gone now due to successful merge!
        sighting1.delete_cascade()
        sighting2.delete_cascade()


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_permissions(
    db, flask_app_client, researcher_1, researcher_2, contributor_1
):
    individual1_id = None
    sighting1 = None
    encounter1 = None
    individual2_id = None
    sighting2 = None
    encounter2 = None
    try:
        sighting1, encounter1 = prep_data(db, flask_app_client, researcher_1)
        individual1_id = str(encounter1.individual_guid)
        sighting2, encounter2 = prep_data(db, flask_app_client, researcher_2)
        individual2_id = str(encounter2.individual_guid)

        # this tests as researcher_2, which should trigger a merge-request (owns just 1 encounter)
        # NOTE: merge_request not yet implmented, so fails accordingly (code 500)
        data_in = [individual2_id]
        response = test_utils.post_via_flask(
            flask_app_client,
            researcher_2,
            scopes=('individuals:write',),
            path=f'/api/v1/individuals/{individual1_id}/merge',
            data=data_in,
            expected_status_code=500,
            response_200={'merged'},
        )
        assert response.json['merge_request']
        assert response.json['message'] == 'Merge failed'
        assert response.json['blocking_encounters'] == [str(encounter1.guid)]

        # a user who owns none (403 fail, no go)
        response = test_utils.post_via_flask(
            flask_app_client,
            contributor_1,
            scopes=('individuals:write',),
            path=f'/api/v1/individuals/{individual1_id}/merge',
            data=data_in,
            expected_status_code=403,
            response_200={'merged'},
        )

        # anonymous (401)
        response = test_utils.post_via_flask(
            flask_app_client,
            None,
            scopes=('individuals:write',),
            path=f'/api/v1/individuals/{individual1_id}/merge',
            data=data_in,
            expected_status_code=401,
            response_200={'merged'},
        )

    finally:
        individual_utils.delete_individual(flask_app_client, researcher_1, individual1_id)
        individual_utils.delete_individual(flask_app_client, researcher_2, individual2_id)
        sighting1.delete_cascade()
        sighting2.delete_cascade()


@pytest.mark.skipif(
    test_utils.module_unavailable(
        'individuals', 'encounters', 'sightings', 'social_groups'
    ),
    reason='Individuals module disabled',
)
def test_merge_social_groups(db, flask_app_client, researcher_1):
    from app.modules.social_groups.models import SocialGroup

    individual1_id = None
    sighting1 = None
    encounter1 = None
    individual2_id = None
    sighting2 = None
    encounter2 = None
    try:
        sighting1, encounter1 = prep_data(db, flask_app_client, researcher_1)
        individual1_id = str(encounter1.individual_guid)
        sighting2, encounter2 = prep_data(db, flask_app_client, researcher_1)
        individual2_id = str(encounter2.individual_guid)

        individual1 = Individual.query.get(individual1_id)
        individual2 = Individual.query.get(individual2_id)

        # this tests target individual is not in social group
        groupA_name = 'groupA'
        groupA_role_from_2 = 'doomed-to-be-merged'
        members = {individual2_id: {'roles': [groupA_role_from_2]}}
        social_groupA = SocialGroup(members, groupA_name)
        with db.session.begin(subtransactions=True):
            db.session.add(social_groupA)

        # this tests target is in group, but gains new role
        groupB_name = 'groupB'
        groupB_role_from_1 = 'roleB1'
        groupB_role_from_2 = 'roleB2'
        members = {
            individual1_id: {'roles': [groupB_role_from_1]},
            individual2_id: {'roles': [groupB_role_from_2]},
        }
        social_groupB = SocialGroup(members, groupB_name)
        db.session.add(social_groupB)

        # this tests target is in group, but shares a role (and will gain a new one)
        groupC_name = 'groupC'
        groupC_shared_role = 'sharedC'
        groupC_role_from_2 = 'roleC2'
        members = {
            individual1_id: {'roles': [groupC_shared_role]},
            individual2_id: {'roles': [groupC_shared_role, groupC_role_from_2]},
        }
        social_groupC = SocialGroup(members, groupC_name)
        db.session.add(social_groupC)

        db.session.merge(individual1)
        db.session.merge(individual2)
        import utool as ut

        ut.embed()

        # now do the merge
        data_in = [individual2_id]
        with flask_app_client.login(researcher_1, auth_scopes=('individuals:write',)):
            response = flask_app_client.post(
                f'/api/v1/individuals/{individual1_id}/merge',
                data=json.dumps(data_in),
                content_type='application/json',
            )
        assert response.status_code == 200

        import utool as ut

        ut.embed()
        assert False

    finally:
        individual_utils.delete_individual(flask_app_client, researcher_1, individual1_id)
        individual_utils.delete_individual(flask_app_client, researcher_1, individual2_id)
        sighting1.delete_cascade()
        sighting2.delete_cascade()
