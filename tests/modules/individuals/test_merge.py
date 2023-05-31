# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import datetime

import pytest

import tests.modules.site_settings.resources.utils as site_setting_utils
from tests import utils as test_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.social_groups.resources import utils as socgrp_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge(db, flask_app_client, researcher_1, request, test_root):

    from app.modules.individuals.models import Individual

    sighting_data = {
        'encounters': [{}, {}, {}],
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
    }

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, sighting_data
    )
    assert len(uuids['encounters']) == len(sighting_data['encounters'])

    enc1_guid = uuids['encounters'][0]
    enc2_guid = uuids['encounters'][1]

    individual_data_in = {
        'names': [{'context': 'text', 'value': 'name-1'}],
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
    indiv1_guid = individual_response.json['guid']

    # now same for 2nd indiv
    individual_data_in['names'][0]['value'] = 'name-2'
    individual_data_in['encounters'][0]['id'] = enc2_guid
    # both will be set female
    individual_response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, individual_data_in
    )
    indiv2_guid = individual_response.json['guid']

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

    try:
        indiv1.merge_from(indiv1)  # fail cuz no merging with self
    except ValueError as ve:
        assert 'with self' in str(ve)

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
    import uuid

    from app.modules.individuals.models import Individual
    from app.modules.social_groups.models import SocialGroup

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
    groupA_role_from_2 = {'guid': str(uuid.uuid4()), 'label': 'doomed-to-be-merged'}
    groupB_role_from_1 = {'guid': str(uuid.uuid4()), 'label': 'roleB1'}
    groupB_role_from_2 = {'guid': str(uuid.uuid4()), 'label': 'roleB2'}
    groupC_shared_role = {'guid': str(uuid.uuid4()), 'label': 'sharedC'}
    groupC_role_from_2 = {'guid': str(uuid.uuid4()), 'label': 'roleC2'}
    role_data = [
        {
            'guid': groupA_role_from_2['guid'],
            'label': groupA_role_from_2['label'],
            'multipleInGroup': False,
        },
        {
            'guid': groupB_role_from_2['guid'],
            'label': groupB_role_from_2['label'],
            'multipleInGroup': True,
        },
        {
            'guid': groupB_role_from_1['guid'],
            'label': groupB_role_from_1['label'],
            'multipleInGroup': True,
        },
        {
            'guid': groupC_shared_role['guid'],
            'label': groupC_shared_role['label'],
            'multipleInGroup': True,
        },
        {
            'guid': groupC_role_from_2['guid'],
            'label': groupC_role_from_2['label'],
            'multipleInGroup': True,
        },
    ]
    socgrp_utils.set_roles(flask_app_client, admin_user, role_data)
    request.addfinalizer(lambda: socgrp_utils.delete_roles(flask_app_client, admin_user))

    # this tests target individual is not in social group
    groupA_name = 'groupA'
    group_data = {
        'name': groupA_name,
        'members': {individual2_id: {'role_guids': [groupA_role_from_2['guid']]}},
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
            individual1_id: {'role_guids': [groupB_role_from_1['guid']]},
            individual2_id: {'role_guids': [groupB_role_from_2['guid']]},
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
            individual1_id: {'role_guids': [groupC_shared_role['guid']]},
            individual2_id: {
                'role_guids': [groupC_shared_role['guid'], groupC_role_from_2['guid']]
            },
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
    assert social_groupB.get_member(individual1_id).roles == [groupB_role_from_1['guid']]
    assert len(social_groupC.members) == 2
    assert social_groupC.get_member(individual1_id).roles == [groupC_shared_role['guid']]

    # now do the merge
    merge_from = [individual2]
    individual1.merge_from(*merge_from)
    individual2 = Individual.query.get(individual2_id)

    # post-merge changes
    assert len(social_groupA.members) == 1
    assert str(social_groupA.members[0].individual_guid) == individual1_id
    assert len(social_groupB.members) == 1
    assert set(social_groupB.get_member(individual1_id).roles) == {
        groupB_role_from_1['guid'],
        groupB_role_from_2['guid'],
    }
    assert len(social_groupC.members) == 1
    assert set(social_groupC.get_member(individual1_id).roles) == {
        groupC_shared_role['guid'],
        groupC_role_from_2['guid'],
    }


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_request_init(db, flask_app_client, researcher_1, researcher_2, request):
    from dateutil import parser as dt_parser

    from app.modules.encounters.models import Encounter
    from app.modules.individuals.models import Individual
    from app.modules.notifications.models import Notification, NotificationType

    conf_tx = site_setting_utils.get_some_taxonomy_dict(flask_app_client, researcher_1)
    # since this is just a simple init-only test, we can use incomplete data (not going to edm etc)
    #   we just want to see that the task starts (it should be ignored and die when triggered in celery)
    Notification.query.delete()
    individual = Individual()
    individual.taxonomy_guid = conf_tx['id']  # tests cdx-8 "default" behavior
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
    # test cdx-8 first with taxonomy override param
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
    assert notif.message_values['deadline']
    deadline = dt_parser.parse(notif.message_values['deadline'])
    assert deadline
    assert (
        'request_id' in notif.message_values
        and notif.message_values['request_id'] == res['async'].id
    )

    notif = Notification.query.filter_by(
        recipient=researcher_2,
        message_type=NotificationType.individual_merge_request,
    ).first()
    assert notif
    assert notif.message_values['deadline']
    deadline = dt_parser.parse(notif.message_values['deadline'])
    assert deadline
    assert (
        'request_id' in notif.message_values
        and notif.message_values['request_id'] == res['async'].id
    )


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_request_init_taxonomy(
    db, flask_app_client, researcher_1, researcher_2, request
):
    from app.modules.encounters.models import Encounter
    from app.modules.individuals.models import Individual
    from app.modules.notifications.models import Notification

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
    # test cdx-8 first with taxonomy override param
    params = {
        'deadline_delta_seconds': 3,
        'test': True,
    }
    # should fail as no taxonomy present
    with pytest.raises(ValueError) as verr:
        res = individual.merge_request_from([individual2], params)
    assert 'must have a taxonomy set or override value' in str(verr.value)
    # now test it with override, which should pass
    conf_tx = site_setting_utils.get_some_taxonomy_dict(flask_app_client, researcher_1)
    params['override'] = {'taxonomy_guid': conf_tx['id']}
    res = individual.merge_request_from([individual2], params)
    assert res
    assert 'async' in res
    assert res['async'].id


@pytest.mark.skipif(
    module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_hash(db, flask_app_client, researcher_1, researcher_2, request):
    from app.modules.encounters.models import Encounter
    from app.modules.individuals.models import Individual

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

    fake_guid = '00000000-0000-0000-0000-ffffffffffff'

    individual1 = Individual()
    try:
        # empty from individuals
        individual1._merge_request_init([])
    except ValueError as ve:
        assert 'invalid individuals' in str(ve)

    # just gets us a (mostly bunk) celery task, so we can test revoked
    deadline = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
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
    assert {individual1, individual2} == set(rtn)


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_merge_names(db, flask_app_client, researcher_1, admin_user, request, test_root):
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
    individual3_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )

    individual1_id = individual1_uuids['individual']
    individual2_id = individual2_uuids['individual']
    individual3_id = individual3_uuids['individual']
    individual1 = Individual.query.get(individual1_id)
    individual2 = Individual.query.get(individual2_id)
    individual3 = Individual.query.get(individual3_id)

    # this tests directly individual.merge_names() which currently is only used
    #   from within merging
    shared_context = 'test-context'
    overridden_context = 'test-override'
    individual1.add_name(shared_context, 'one', researcher_1)
    individual1.add_name('another', 'another', researcher_1)
    # blown away by override
    individual1.add_name(overridden_context, 'gone1', researcher_1)
    # should get bumped to have 1 suffix
    individual2.add_name(shared_context, 'two', researcher_1)
    # blown away by override
    individual2.add_name(overridden_context, 'gone2', researcher_1)
    # should get bumped to have 2 suffix
    individual3.add_name(shared_context, 'three', researcher_1)
    individual3.add_name('third', '333', researcher_1)
    assert len(individual1.names) == 3
    assert len(individual2.names) == 2
    assert len(individual3.names) == 2

    individual1.merge_names([individual2, individual3], {overridden_context: 'winner'})
    assert len(individual1.names) == 6
    assert len(individual2.names) == 1  # overridden one is left behind to die
    assert len(individual3.names) == 0
    assert {
        shared_context,
        f'{shared_context}1',
        f'{shared_context}2',
        'another',
        'third',
        overridden_context,
    } == {name.context for name in individual1.names}

    # test fail_on_conflict flag (currently not used anywhere) - should raise ValueError
    individual4_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual4_id = individual4_uuids['individual']
    individual4 = Individual.query.get(individual4_id)
    individual4.add_name(shared_context, 'break', researcher_1)
    try:
        individual1.merge_names([individual4], fail_on_conflict=True)
    except ValueError as ve:
        assert str(ve).startswith(f'conflict on context {shared_context}')
    assert len(individual1.names) == 6
    assert len(individual4.names) == 1

    # now we try as a part of an actual merge, with an override as well
    individual2_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual3_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual2_id = individual2_uuids['individual']
    individual3_id = individual3_uuids['individual']
    individual2 = Individual.query.get(individual2_id)
    individual3 = Individual.query.get(individual3_id)
    # both of these should be ignored via override
    individual2.add_name(shared_context, 'AAA', researcher_1)
    individual3.add_name(shared_context, 'BBB', researcher_1)
    individual3.add_name('endearment', 'sweetie', researcher_1)  # will get added
    assert len(individual2.names) == 1
    assert len(individual3.names) == 2

    final_value = 'final-value'
    merge_from = [individual2, individual3]
    parameters = {'override': {'name_context': {shared_context: final_value}}}
    individual1.merge_from(*merge_from, parameters=parameters)
    assert len(individual1.names) == 7  # original 6 (one swapped out - override) + 1 new
    assert len(individual2.names) == 0
    assert len(individual3.names) == 0
    # verify override one stuck
    found = False
    for name in individual1.names:
        if name.context == shared_context and name.value == final_value:
            found = True
    assert found
