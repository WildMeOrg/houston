# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_res_utils
from tests.modules.individuals import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest
from tests import utils as test_utils

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge(db, flask_app_client, researcher_1):

    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting
    from app.modules.individuals.models import Individual

    data_in = {
        'encounters': [
            {
                'locationId': 'one',
            },
            {
                'locationId': 'two',
            },
            {
                'locationId': 'three',
            },
        ],
        'startTime': '2000-01-01T01:01:01Z',
        'locationId': 'test',
    }

    response = sighting_utils.create_sighting(flask_app_client, researcher_1, data_in)
    enc1_guid = response.json['result']['encounters'][0]['id']
    enc2_guid = response.json['result']['encounters'][1]['id']
    enc3_guid = response.json['result']['encounters'][2]['id']
    enc1 = Encounter.query.get(enc1_guid)
    enc2 = Encounter.query.get(enc1_guid)
    sighting = Sighting.query.get(response.json['result']['id'])

    individual_data_in = {
        'names': {'defaultName': 'NAME1'},
        'encounters': [
            {
                'id': enc1_guid,
            }
        ],
        'sex': 'female',
    }
    individual_response = individual_res_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    indiv1_guid = individual_response.json['result']['id']

    # now same for 2nd indiv
    individual_data_in['names']['defaultName'] = 'NAME2'
    individual_data_in['encounters'][0]['id'] = enc2_guid
    # both will be set female
    individual_response = individual_res_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    indiv2_guid = individual_response.json['result']['id']

    indiv1 = Individual.query.get(indiv1_guid)
    indiv2 = Individual.query.get(indiv2_guid)
    assert indiv1 is not None
    assert indiv2 is not None
    assert str(indiv1.encounters[0].guid) == enc1_guid
    assert str(indiv2.encounters[0].guid) == enc2_guid

    try:
        indiv1.merge_from()  # fail cuz no source-individuals
    except ValueError as ve:
        assert 'at least 1' in str(ve)

    indiv1.merge_from(indiv2)

    assert len(indiv1.encounters) == 2
    indiv2 = Individual.query.get(indiv2_guid)  # should be gone
    assert not indiv2

    # now a 3rd indiv with sex=male
    individual_data_in['sex'] = 'male'
    individual_data_in['names']['defaultName'] = 'NAME3'
    individual_data_in['encounters'][0]['id'] = enc3_guid
    individual_response = individual_res_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    indiv3_guid = individual_response.json['result']['id']

    indiv3 = Individual.query.get(indiv3_guid)
    assert str(indiv3.encounters[0].guid) == enc3_guid
    enc3 = Encounter.query.get(enc3_guid)
    assert enc3.individual_guid == indiv3.guid

    resp = indiv1.merge_from(indiv3)
    assert not resp.ok
    assert resp.status_code == 500
    json = resp.json()
    assert 'errorFields' in json
    assert 'sex' in json['errorFields']

    individual_res_utils.delete_individual(flask_app_client, researcher_1, indiv1.guid)
    # individual_res_utils.delete_individual(flask_app_client, researcher_1, indiv2.guid)  # actually gone by way of merge!
    individual_res_utils.delete_individual(flask_app_client, researcher_1, indiv3.guid)
    sighting.delete_cascade()
    enc1.delete_cascade()
    enc2.delete_cascade()
    enc3.delete_cascade()


@pytest.mark.skipif(
    test_utils.module_unavailable(
        'individuals', 'encounters', 'sightings', 'social_groups'
    ),
    reason='Individuals module disabled',
)
def test_merge_social_groups(db, flask_app_client, researcher_1):
    from app.modules.social_groups.models import SocialGroup
    from app.modules.individuals.models import Individual

    individual1_id = None
    sighting1 = None
    encounter1 = None
    individual2_id = None
    sighting2 = None
    encounter2 = None
    try:
        sighting1, encounter1 = individual_utils.simple_sighting_encounter(
            db, flask_app_client, researcher_1
        )
        individual1_id = str(encounter1.individual_guid)
        sighting2, encounter2 = individual_utils.simple_sighting_encounter(
            db, flask_app_client, researcher_1
        )
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

        # pre-merge sanity check
        assert len(social_groupA.members) == 1
        assert str(social_groupA.members[0].individual_guid) == individual2_id
        assert len(social_groupB.members) == 2
        assert social_groupB.get_member(individual1_id).roles == [groupB_role_from_1]
        assert len(social_groupC.members) == 2
        assert social_groupC.get_member(individual1_id).roles == [groupC_shared_role]

        # now do the merge
        merge_from = [individual2]
        individual1.merge_from(*merge_from)
        individual2 = Individual.query.get(individual2_id)

        # post-merge changes
        assert len(social_groupA.members) == 1
        assert str(social_groupA.members[0].individual_guid) == individual1_id
        assert len(social_groupB.members) == 1
        assert set(social_groupB.get_member(individual1_id).roles) == set(
            [groupB_role_from_1, groupB_role_from_2]
        )
        assert len(social_groupC.members) == 1
        assert set(social_groupC.get_member(individual1_id).roles) == set(
            [groupC_shared_role, groupC_role_from_2]
        )

    finally:
        individual_res_utils.delete_individual(
            flask_app_client, researcher_1, individual1_id
        )
        sighting1.delete_cascade()
        sighting2.delete_cascade()
