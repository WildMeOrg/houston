# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.social_groups.resources import utils as socgrp_utils
import pytest
from tests import utils as test_utils

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge(db, flask_app_client, researcher_1, request, test_root):
    from app.modules.individuals.models import Individual

    sighting_data = {
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

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, sighting_data
    )
    assert len(uuids['encounters']) == len(sighting_data['encounters'])

    enc1_guid = uuids['encounters'][0]
    enc2_guid = uuids['encounters'][1]

    individual_data_in = {
        'names': {'defaultName': 'NAME1'},
        'encounters': [
            {
                'id': enc1_guid,
            }
        ],
        'sex': 'female',
    }
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    indiv1_guid = individual_response.json['result']['id']

    # now same for 2nd indiv
    individual_data_in['names']['defaultName'] = 'NAME2'
    individual_data_in['encounters'][0]['id'] = enc2_guid
    # both will be set female
    individual_response = individual_utils.create_individual(
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
        lambda: individual_utils.delete_individual(
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


@pytest.mark.skipif(
    test_utils.module_unavailable(
        'individuals', 'encounters', 'sightings', 'social_groups'
    ),
    reason='Individuals module disabled',
)
def test_merge_social_groups(
    db, flask_app_client, researcher_1, admin_user, request, test_root
):
    from app.modules.social_groups.models import SocialGroup
    from app.modules.individuals.models import Individual

    individual1_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual2_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )

    individual1_id = individual1_uuids['individual']
    individual2_id = individual2_uuids['individual']

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
def test_merge_request_init(db, flask_app_client, researcher_1, researcher_2, request):
    from app.modules.individuals.models import Individual
    from app.modules.encounters.models import Encounter
    from app.modules.notifications.models import Notification, NotificationType

    # since this is just a simple init-only test, we can use incomplete data (not going to edm etc)
    #   we just want to see that the task starts (it should be ignored and die when triggered in celery)
    Notification.query.delete()
    individual = Individual()
    enc = Encounter()
    enc.owner = researcher_1
    individual.add_encounter(enc)
    request.addfinalizer(enc.delete_cascade)
    request.addfinalizer(individual.delete)
    individual2 = Individual()
    enc = Encounter()
    enc.owner = researcher_2
    individual2.add_encounter(enc)
    request.addfinalizer(enc.delete_cascade)
    request.addfinalizer(individual2.delete)
    params = {
        'deadline_delta_seconds': 3,
        'test': True,
    }
    res = individual.merge_request_from([individual2], params)
    print(f'>>> {individual} queued via {res}')
    assert res
    assert 'async' in res
    assert res['async'].id

    request.addfinalizer(Notification.query.delete)
    notif = Notification.query.filter_by(
        recipient=researcher_1,
        message_type=NotificationType.individual_merge_request,
    ).first()
    assert notif

    assert (
        'request_id' in notif.message_values
        and notif.message_values['request_id'] == res['async'].id
    )
    notif = Notification.query.filter_by(
        recipient=researcher_2,
        message_type=NotificationType.individual_merge_request,
    ).first()
    assert notif
    assert (
        'request_id' in notif.message_values
        and notif.message_values['request_id'] == res['async'].id
    )


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_hash(db, flask_app_client, researcher_1, researcher_2, request):
    from app.modules.individuals.models import Individual
    from app.modules.encounters.models import Encounter

    individual1 = Individual()
    enc1 = Encounter()
    enc1.owner = researcher_1
    individual1.add_encounter(enc1)
    request.addfinalizer(enc1.delete_cascade)
    request.addfinalizer(individual1.delete)
    individual2 = Individual()
    enc2 = Encounter()
    enc2.owner = researcher_2
    individual2.add_encounter(enc2)
    request.addfinalizer(enc2.delete_cascade)
    request.addfinalizer(individual2.delete)
    hash_start = Individual.merge_request_hash([individual1, individual2])

    enc1.owner = researcher_2
    hash1 = Individual.merge_request_hash([individual1, individual2])
    assert hash_start != hash1

    enc2.individual = None
    hash2 = Individual.merge_request_hash([individual1, individual2])
    assert hash_start != hash2
    assert hash1 != hash2

    enc3 = Encounter()
    enc3.owner = researcher_2
    individual2.add_encounter(enc3)
    request.addfinalizer(enc3.delete_cascade)
    hash3 = Individual.merge_request_hash([individual1, individual2])
    assert hash_start != hash3
    assert hash1 != hash2
    assert hash1 != hash3
    assert hash2 != hash3


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_failure_cases(db, flask_app_client, researcher_1, request):
    from app.modules.individuals.models import Individual
    from app.modules.individuals.tasks import execute_merge_request
    from datetime import datetime, timedelta

    fake_guid = '00000000-0000-0000-0000-ffffffffffff'

    individual1 = Individual()
    try:
        # empty from individuals
        individual1._merge_request_init([])
    except ValueError as ve:
        assert 'invalid individuals' in str(ve)

    # just gets us a (mostly bunk) celery task, so we can test revoked
    deadline = datetime.utcnow() + timedelta(minutes=5)
    async_res = execute_merge_request.apply_async(
        (str(individual1.guid), [], {}), eta=deadline
    )
    celery_running = False
    try:
        data = Individual.get_merge_request_data(async_res.id)
        assert data
        assert 'request' in data
        assert data['request'].get('id') == async_res.id
        celery_running = True
    except NotImplementedError:  # in case celery is not running
        pass

    if celery_running:
        async_res.revoke()
        # now data should be empty
        data = Individual.get_merge_request_data(async_res.id)
        assert not data
        data = Individual.get_merge_request_data(fake_guid)
        assert not data
        rtn = Individual.validate_merge_request(fake_guid, [])
        assert not rtn
        rtn = Individual.validate_merge_request(str(individual1.guid), [fake_guid])
        assert not rtn

    # check invalid due to hash
    individual2 = Individual()
    with db.session.begin():
        db.session.add(individual1)
        db.session.add(individual2)
    request.addfinalizer(individual1.delete)
    request.addfinalizer(individual2.delete)
    real_hash = Individual.merge_request_hash([individual1, individual2])
    params = {'checksum': 1}
    rtn = Individual.validate_merge_request(
        str(individual1.guid), [str(individual2.guid)], params
    )
    assert not rtn
    # ok, not truly a failure case
    params = {'checksum': real_hash}
    rtn = Individual.validate_merge_request(
        str(individual1.guid), [str(individual2.guid)], params
    )
    assert rtn
    assert len(rtn) == 2
    assert set([individual1, individual2]) == set(rtn)
