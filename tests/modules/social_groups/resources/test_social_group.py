# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging
import uuid

import pytest

import tests.modules.audit_logs.resources.utils as audit_utils
import tests.modules.individuals.resources.utils as individual_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.modules.social_groups.resources.utils as soc_group_utils
from tests import utils as test_utils
from tests.utils import module_unavailable

log = logging.getLogger(__name__)


# Needs to be a separate method as if you call the addfinalizer in a loop, it only deleted the last one
def add_individual(flask_app_client, user, request, enc_id):
    encounter_json = {'encounters': [{'id': enc_id}]}
    resp = individual_utils.create_individual(
        flask_app_client,
        user,
        data_in=encounter_json,
    )

    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, user, resp.json['guid']
        )
    )
    return resp.json


def create_individuals(flask_app_client, user, request, test_root, num_individuals=3):

    # Create a sighting with three encounters
    sighting_data = {
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'locationId': 'test social groups',
        'encounters': [],
    }
    for enc_id in range(0, num_individuals):
        sighting_data['encounters'].append({'locationId': f'loc{enc_id}'})

    uuids = sighting_utils.create_sighting(
        flask_app_client, user, request, test_root, sighting_data
    )

    assert len(uuids['encounters']) == num_individuals

    # Create the individuals to use in testing
    individuals = []
    for ind_num in range(0, num_individuals):
        individuals.append(
            add_individual(flask_app_client, user, request, uuids['encounters'][ind_num])
        )

    return individuals


def get_matriarch_and_git_guids(flask_app_client, admin_user):
    current_roles = soc_group_utils.get_roles(flask_app_client, admin_user)

    assert {'Matriarch', 'IrritatingGit'} == {role['label'] for role in current_roles}
    matriarch_guid = None
    irritating_git_guid = None
    for role in current_roles:
        if role['label'] == 'Matriarch':
            matriarch_guid = role['guid']
        elif role['label'] == 'IrritatingGit':
            irritating_git_guid = role['guid']
    assert matriarch_guid
    assert irritating_git_guid
    return matriarch_guid, irritating_git_guid


@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_basic_operation(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request, test_root
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user, request)
    # and get the guids
    matriarch_guid, git_guid = get_matriarch_and_git_guids(flask_app_client, admin_user)

    # Create some individuals to use in testing
    individuals = create_individuals(flask_app_client, researcher_1, request, test_root)

    # Create a social group for them
    data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }
    group_resp = soc_group_utils.create_social_group(
        flask_app_client, researcher_1, data, request=request
    )
    group_guid = group_resp.json['guid']

    # read it
    soc_group_utils.read_social_group(flask_app_client, researcher_1, group_guid)
    group_as_res_2 = soc_group_utils.read_social_group(
        flask_app_client, researcher_2, group_guid
    )
    soc_group_utils.validate_response(data, group_as_res_2.json)

    groups_as_res_2 = soc_group_utils.read_all_social_groups(
        flask_app_client, researcher_2
    )
    assert len(groups_as_res_2.json) >= 1

    # get and validate the audit logs for the social group
    audit = audit_utils.read_audit_log(flask_app_client, admin_user, group_guid)
    assert len(audit.json) == 1
    create_log = audit.json[0]
    assert create_log['module_name'] == 'SocialGroup'
    assert create_log['user_email'] == researcher_1.email

    # validate that the individual GET includes the social group
    individual_as_res1_json = individual_utils.read_individual(
        flask_app_client, researcher_1, individuals[0]['id']
    ).json
    assert len(individual_as_res1_json['social_groups']) == 1
    ind_social_group = individual_as_res1_json['social_groups'][0]
    assert individuals[0]['id'] in ind_social_group['members']
    assert data['name'] == ind_social_group['name']


# Test invalid configuration options. The API is via site settings but the validation is in SocialGroup so
# this is a social group test
@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_error_config(flask_app_client, researcher_1, admin_user):
    import uuid

    valid_data = [
        {'guid': str(uuid.uuid4()), 'label': 'Matriarch', 'multipleInGroup': False},
        {'guid': str(uuid.uuid4()), 'label': 'IrritatingGit', 'multipleInGroup': True},
    ]

    # Valid data but non admin user so should fail
    error = "You don't have the permission to access the requested resource."
    soc_group_utils.set_roles(flask_app_client, researcher_1, valid_data, 403, error)

    missing_field = [
        {'guid': str(uuid.uuid4()), 'label': 'Matriarch'},
        {'guid': str(uuid.uuid4()), 'label': 'IrritatingGit', 'multipleInGroup': True},
    ]

    resp = soc_group_utils.set_roles(flask_app_client, admin_user, missing_field, 400)
    # cant rely on order of keys so just test something
    assert 'Role dictionary must have the following keys' in resp.json['message']

    extra_field = [
        {
            'guid': str(uuid.uuid4()),
            'label': 'Matriarch',
            'multipleInGroup': False,
            'attitude': True,
        },
        {'guid': str(uuid.uuid4()), 'label': 'IrritatingGit', 'multipleInGroup': True},
    ]

    resp = soc_group_utils.set_roles(flask_app_client, admin_user, extra_field, 400)
    assert 'Role dictionary must have the following keys' in resp.json['message']

    duplicate_label = [
        {'guid': str(uuid.uuid4()), 'label': 'Matriarch', 'multipleInGroup': False},
        {'guid': str(uuid.uuid4()), 'label': 'Matriarch', 'multipleInGroup': True},
    ]
    error = 'can only have Matriarch once'
    soc_group_utils.set_roles(flask_app_client, admin_user, duplicate_label, 400, error)

    missing_guid = [
        {'guid': str(uuid.uuid4()), 'label': 'Matriarch'},
        {'label': 'Mild mannered janitor'},
    ]
    resp = soc_group_utils.set_roles(flask_app_client, admin_user, missing_guid, 400)
    # cant rely on order of keys so just test something
    assert 'Role dictionary must have the following keys' in resp.json['message']


@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_invalid_creation(
    db,
    flask_app_client,
    researcher_1,
    researcher_2,
    admin_user,
    regular_user,
    request,
    test_root,
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user, request)
    # and get the guids
    matriarch_guid, git_guid = get_matriarch_and_git_guids(flask_app_client, admin_user)

    # Create some individuals to use in testing
    individuals = create_individuals(flask_app_client, researcher_1, request, test_root)

    valid_data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }
    # Shouldn't work with anon user
    error = (
        'The server could not verify that you are authorized to access the URL requested. You either supplied '
        "the wrong credentials (e.g. a bad password), or your browser doesn't understand how to supply the "
        'credentials required.'
    )
    soc_group_utils.create_social_group(flask_app_client, None, valid_data, 401, error)

    # or contributor
    error = "You don't have the permission to access the requested resource."
    soc_group_utils.create_social_group(
        flask_app_client, regular_user, valid_data, 403, error
    )

    missing_name = {
        'members': {
            individuals[0]['id']: {'role_guids': matriarch_guid},
            individuals[1]['id']: {},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }
    error = 'The request was formatted correctly but contains a semantic error (check input values and types).'
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, missing_name, 422, error
    )

    invalid_fields = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {'attitude': 'Stubborn'},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }
    error = (
        f"Social Group member {individuals[1]['id']} fields not supported {{'attitude'}}"
    )
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, invalid_fields, 400, error
    )

    random_guid = str(uuid.uuid4())
    invalid_guid = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            random_guid: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }
    error = f'Social Group member {random_guid} does not match an individual'
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, invalid_guid, 400, error
    )

    # Can have multiple gits
    many_gits = {
        'name': 'Many gits',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {'role_guids': [git_guid]},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }

    group_resp = soc_group_utils.create_social_group(
        flask_app_client, researcher_1, many_gits, request=request
    )
    soc_group_utils.validate_response(many_gits, group_resp.json)

    # But only one matriarch
    many_matriarchs = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {'role_guids': [matriarch_guid]},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }
    error = 'Can only have one Matriarch in a group'
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, many_matriarchs, 400, error
    )

    # User can have multiple_roles
    many_roles = {
        'name': 'Many roles',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid, git_guid]},
            individuals[1]['id']: {'role_guids': [git_guid]},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }
    group_resp = soc_group_utils.create_social_group(
        flask_app_client, researcher_1, many_roles, request=request
    )
    soc_group_utils.validate_response(many_roles, group_resp.json)


@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_role_changes(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request, test_root
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user, request)
    # and get the guids
    matriarch_guid, git_guid = get_matriarch_and_git_guids(flask_app_client, admin_user)

    # Create some individuals to use in testing
    individuals = create_individuals(flask_app_client, researcher_1, request, test_root)

    valid_group = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {'role_guids': [git_guid]},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }

    group_resp = soc_group_utils.create_social_group(
        flask_app_client, researcher_1, valid_group, request=request
    ).json
    group_guid = group_resp['guid']

    # Social group was created, now change the config and see what changes
    changed_config = [
        {'guid': git_guid, 'label': 'IrritatingGit', 'multipleInGroup': False},
    ]

    soc_group_utils.set_roles(flask_app_client, admin_user, changed_config)

    group_as_res_2 = soc_group_utils.read_social_group(
        flask_app_client, researcher_2, group_guid
    ).json

    for member_guid in valid_group['members']:
        assert member_guid in group_as_res_2['members']
        if matriarch_guid in valid_group['members'][member_guid]['role_guids']:
            assert (
                matriarch_guid not in group_as_res_2['members'][member_guid]['role_guids']
            )
        elif git_guid in valid_group['members'][member_guid]['role_guids']:
            assert git_guid in group_as_res_2['members'][member_guid]['role_guids']


@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_patch(
    db,
    flask_app_client,
    researcher_1,
    researcher_2,
    regular_user,
    admin_user,
    request,
    test_root,
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user, request)
    # and get the guids
    matriarch_guid, git_guid = get_matriarch_and_git_guids(flask_app_client, admin_user)

    # Create some individuals to use in testing
    individuals = create_individuals(
        flask_app_client, researcher_1, request, test_root, num_individuals=4
    )

    valid_group = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {'role_guids': [git_guid]},
            individuals[2]['id']: {'role_guids': [git_guid]},
        },
    }

    group_resp = soc_group_utils.create_social_group(
        flask_app_client, researcher_1, valid_group, request=request
    )
    group_guid = group_resp.json['guid']
    patch_name = [test_utils.patch_add_op('name', 'different reprobates')]

    soc_group_utils.patch_social_group(
        flask_app_client,
        researcher_2,
        group_guid,
        patch_name,
    )
    group_data = soc_group_utils.read_social_group(
        flask_app_client, researcher_1, group_guid
    )
    assert group_data.json['name'] == 'different reprobates'

    different_members = {
        individuals[1]['id']: {'role_guids': [matriarch_guid]},
        individuals[3]['id']: {'role_guids': [git_guid]},
    }
    patch_all_members = [test_utils.patch_replace_op('members', different_members)]

    # should not be allowed by regular user
    access_error = "You don't have the permission to access the requested resource."
    soc_group_utils.patch_social_group(
        flask_app_client, regular_user, group_guid, patch_all_members, 403, access_error
    )
    # but should for researcher 1
    soc_group_utils.patch_social_group(
        flask_app_client, researcher_1, group_guid, patch_all_members
    )
    group_data = soc_group_utils.read_social_group(
        flask_app_client, researcher_1, group_guid
    )
    soc_group_utils.validate_members(different_members, group_data.json['members'])

    # can't patch in member as regular_user
    patch_add_matriarch = [
        test_utils.patch_add_op(
            'members', {individuals[2]['id']: {'role_guids': [matriarch_guid]}}
        )
    ]
    soc_group_utils.patch_social_group(
        flask_app_client, regular_user, group_guid, patch_add_matriarch, 403, access_error
    )
    # but can as researcher_1, should still fail as breaks the one Matriach rule
    error = 'Can only have one Matriarch in a group'
    soc_group_utils.patch_social_group(
        flask_app_client, researcher_1, group_guid, patch_add_matriarch, 400, error
    )

    # Patch with a non-uuid individual guid
    patch_add_error = [
        test_utils.patch_add_op(
            'members',
            {'4037': {'role_guids': [matriarch_guid]}},
        ),
    ]
    invalid_uuid_error = 'Social Group member 4037 needs to be a valid uuid'
    soc_group_utils.patch_social_group(
        flask_app_client,
        researcher_2,
        group_guid,
        patch_add_error,
        400,
        invalid_uuid_error,
    )

    # remove the existing matriarch, any researcher can do that
    patch_remove_matriarch = [test_utils.patch_remove_op('members', individuals[1]['id'])]
    soc_group_utils.patch_social_group(
        flask_app_client, researcher_2, group_guid, patch_remove_matriarch
    )
    group_data = soc_group_utils.read_social_group(
        flask_app_client, researcher_1, group_guid
    )
    assert individuals[1]['id'] not in group_data.json['members']

    # Can now add the new matriarch
    soc_group_utils.patch_social_group(
        flask_app_client,
        researcher_1,
        group_guid,
        patch_add_matriarch,
    )
    group_data = soc_group_utils.read_social_group(
        flask_app_client, researcher_1, group_guid
    )
    assert individuals[2]['id'] in group_data.json['members']
    assert group_data.json['members'][individuals[2]['id']]['role_guids'] == [
        matriarch_guid
    ]

    patch_make_irritating = [
        test_utils.patch_replace_op(
            'members',
            {individuals[2]['id']: {'role_guids': [matriarch_guid, git_guid]}},
        )
    ]
    soc_group_utils.patch_social_group(
        flask_app_client, researcher_1, group_guid, patch_make_irritating
    )

    group_data = soc_group_utils.read_social_group(
        flask_app_client, researcher_1, group_guid
    )
    assert group_data.json['members'][individuals[2]['id']]['role_guids'] == [
        matriarch_guid,
        git_guid,
    ]


@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_individual_delete(
    db, flask_app_client, researcher_1, admin_user, request, test_root
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user, request)
    # and get the guids
    matriarch_guid, git_guid = get_matriarch_and_git_guids(flask_app_client, admin_user)

    # Create some individuals to use in testing
    individuals = create_individuals(flask_app_client, researcher_1, request, test_root)

    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client, researcher_1, request, test_root
    )
    new_individual_uuid = uuids['individual']

    # Create a social group for them
    data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'role_guids': [matriarch_guid]},
            individuals[1]['id']: {},
            individuals[2]['id']: {'role_guids': [git_guid]},
            new_individual_uuid: {},
        },
    }
    group_resp = soc_group_utils.create_social_group(
        flask_app_client, researcher_1, data, request=request
    )
    group_guid = group_resp.json['guid']

    # delete individual and make sure they go away from the group
    individual_utils.delete_individual(
        flask_app_client, researcher_1, new_individual_uuid
    )
    new_data = data
    del new_data['members'][new_individual_uuid]
    # read it
    later_group = soc_group_utils.read_social_group(
        flask_app_client, researcher_1, group_guid
    )
    soc_group_utils.validate_response(new_data, later_group.json)
