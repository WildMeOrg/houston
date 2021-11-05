# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_res_utils
from tests.modules.individuals import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.social_groups.resources import utils as socgrp_utils
import pytest
from tests import utils as test_utils

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge(db, flask_app_client, researcher_1, request):

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

    request.addfinalizer(sighting.delete_cascade)
    request.addfinalizer(enc1.delete_cascade)
    request.addfinalizer(enc2.delete_cascade)

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
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_1, indiv1.guid
        )
    )

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
    request.addfinalizer(enc3.delete_cascade)
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_1, indiv3.guid
        )
    )

    resp = indiv1.merge_from(indiv3)
    assert not resp.ok
    assert resp.status_code == 500
    json = resp.json()
    assert 'errorFields' in json
    assert 'sex' in json['errorFields']


@pytest.mark.skipif(
    test_utils.module_unavailable(
        'individuals', 'encounters', 'sightings', 'social_groups'
    ),
    reason='Individuals module disabled',
)
def test_merge_social_groups(db, flask_app_client, researcher_1, admin_user, request):
    from app.modules.social_groups.models import SocialGroup
    from app.modules.individuals.models import Individual

    individual1_id = None
    sighting1 = None
    encounter1 = None
    individual2_id = None
    sighting2 = None
    encounter2 = None
    sighting1, encounter1 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_1
    )
    request.addfinalizer(sighting1.delete_cascade)
    individual1_id = str(encounter1.individual_guid)
    sighting2, encounter2 = individual_utils.simple_sighting_encounter(
        db, flask_app_client, researcher_1
    )
    request.addfinalizer(sighting2.delete_cascade)
    request.addfinalizer(
        lambda: individual_res_utils.delete_individual(
            flask_app_client, researcher_1, individual1_id
        )
    )
    individual2_id = str(encounter2.individual_guid)

    individual1 = Individual.query.get(individual1_id)
    individual2 = Individual.query.get(individual2_id)

    # set up roles
    role_data = {'key': 'social_group_roles', 'data': {}}
    groupA_role_from_2 = 'doomed-to-be-merged'
    role_data['data'][groupA_role_from_2] = {'multipleInGroup': False}
    groupB_role_from_1 = 'roleB1'
    role_data['data'][groupB_role_from_1] = {'multipleInGroup': True}
    groupB_role_from_2 = 'roleB2'
    role_data['data'][groupB_role_from_2] = {'multipleInGroup': True}
    groupC_shared_role = 'sharedC'
    role_data['data'][groupC_shared_role] = {'multipleInGroup': True}
    groupC_role_from_2 = 'roleC2'
    role_data['data'][groupC_role_from_2] = {'multipleInGroup': True}
    socgrp_utils.set_roles(flask_app_client, admin_user, role_data)
    request.addfinalizer(lambda: socgrp_utils.delete_roles(flask_app_client, admin_user))

    # this tests target individual is not in social group
    groupA_name = 'groupA'
    group_data = {
        'name': groupA_name,
        'members': {individual2_id: {'roles': [groupA_role_from_2]}},
    }
    group_res = socgrp_utils.create_social_group(
        flask_app_client, researcher_1, group_data
    )
    social_groupA = SocialGroup.query.get(group_res.json['guid'])

    # this tests target is in group, but gains new role
    groupB_name = 'groupB'
    group_data = {
        'name': groupB_name,
        'members': {
            individual1_id: {'roles': [groupB_role_from_1]},
            individual2_id: {'roles': [groupB_role_from_2]},
        },
    }
    group_res = socgrp_utils.create_social_group(
        flask_app_client, researcher_1, group_data
    )
    social_groupB = SocialGroup.query.get(group_res.json['guid'])

    # this tests target is in group, but shares a role (and will gain a new one)
    groupC_name = 'groupC'
    group_data = {
        'name': groupC_name,
        'members': {
            individual1_id: {'roles': [groupC_shared_role]},
            individual2_id: {'roles': [groupC_shared_role, groupC_role_from_2]},
        },
    }
    group_res = socgrp_utils.create_social_group(
        flask_app_client, researcher_1, group_data
    )
    social_groupC = SocialGroup.query.get(group_res.json['guid'])

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


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_request(db, flask_app_client, researcher_1):
    from app.modules.individuals.models import Individual

    individual = Individual()
    res = individual._merge_request_init()
    print(f'############## {individual} queued via {res}')
    assert res
    assert 'async' in res
