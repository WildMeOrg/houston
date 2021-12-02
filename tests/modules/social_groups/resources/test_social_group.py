# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging
import uuid
import pytest
from tests.utils import module_unavailable

import tests.modules.social_groups.resources.utils as soc_group_utils
import tests.modules.individuals.resources.utils as individual_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.modules.audit_logs.resources.utils as audit_utils
from tests import utils as test_utils

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
            flask_app_client, user, resp.json['result']['id']
        )
    )
    return resp.json['result']


def create_individuals(flask_app_client, user, request, test_root, num_individuals=3):

    # Create a sighting with three encounters
    sighting_data = {
        'startTime': '2000-01-01T01:01:01Z',
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


@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_basic_operation(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request, test_root
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user, request)

    # Create some individuals to use in testing
    individuals = create_individuals(flask_app_client, researcher_1, request, test_root)

    # Create a social group for them
    data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
    audit = audit_utils.read_audit_log(flask_app_client, researcher_1, group_guid)
    assert len(audit.json) == 1
    create_log = audit.json[0]
    assert create_log['module_name'] == 'SocialGroup'
    assert create_log['user_email'] == researcher_1.email


# Test invalid configuration options. The API is via site settings but the validation is in SocialGroup so
# this is a social group test
@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_error_config(flask_app_client, researcher_1, admin_user):
    valid_data = {
        'key': 'social_group_roles',
        'data': {
            'Matriarch': {'multipleInGroup': False},
            'IrritatingGit': {'multipleInGroup': True},
        },
    }

    # Valid data but non admin user so should fail
    error = "You don't have the permission to access the requested resource."
    soc_group_utils.set_roles(flask_app_client, researcher_1, valid_data, 403, error)

    missing_field = {
        'key': 'social_group_roles',
        'data': {
            'Matriarch': {},
            'IrritatingGit': {'multipleInGroup': True},
        },
    }
    error = "Role dictionary must have the following keys : {'multipleInGroup'}"
    soc_group_utils.set_roles(flask_app_client, admin_user, missing_field, 400, error)

    extra_field = {
        'key': 'social_group_roles',
        'data': {
            'Matriarch': {'multipleInGroup': False, 'attitude': True},
            'IrritatingGit': {'multipleInGroup': True},
        },
    }
    soc_group_utils.set_roles(flask_app_client, admin_user, extra_field, 400, error)


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

    # Create some individuals to use in testing
    individuals = create_individuals(flask_app_client, researcher_1, request, test_root)

    valid_data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
            individuals[0]['id']: {'roles': 'Matriarch'},
            individuals[1]['id']: {},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
        },
    }
    error = 'The request was well-formed but was unable to be followed due to semantic errors.'
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, missing_name, 422, error
    )

    invalid_fields = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {'attitude': 'Stubborn'},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
            random_guid: {'roles': ['Matriarch']},
            individuals[1]['id']: {},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {'roles': ['IrritatingGit']},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {'roles': ['Matriarch']},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
            individuals[0]['id']: {'roles': ['Matriarch', 'IrritatingGit']},
            individuals[1]['id']: {'roles': ['IrritatingGit']},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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

    current_roles = soc_group_utils.get_roles(flask_app_client, admin_user)
    assert 'data' in current_roles.json

    assert set({'Matriarch', 'IrritatingGit'}) == set(current_roles.json['data'].keys())

    # Create some individuals to use in testing
    individuals = create_individuals(flask_app_client, researcher_1, request, test_root)

    valid_group = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {'roles': ['IrritatingGit']},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
        },
    }

    group_resp = soc_group_utils.create_social_group(
        flask_app_client, researcher_1, valid_group, request=request
    )
    group_guid = group_resp.json['guid']

    # Social group was created, now change the config and see what changes
    changed_config = {
        'key': 'social_group_roles',
        'data': {
            'IrritatingGit': {'multipleInGroup': False},
        },
    }

    soc_group_utils.set_roles(flask_app_client, admin_user, changed_config)

    group_as_res_2 = soc_group_utils.read_social_group(
        flask_app_client, researcher_2, group_guid
    )

    for member_guid in valid_group['members']:
        assert member_guid in group_as_res_2.json['members']
        if 'Matriarch' in valid_group['members'][member_guid]['roles']:
            assert 'Matriarch' not in group_as_res_2.json['members'][member_guid]['roles']
        elif 'IrritatingGit' in valid_group['members'][member_guid]['roles']:
            assert 'IrritatingGit' in group_as_res_2.json['members'][member_guid]['roles']


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

    # Create some individuals to use in testing
    individuals = create_individuals(
        flask_app_client, researcher_1, request, test_root, num_individuals=4
    )

    valid_group = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {'roles': ['IrritatingGit']},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
        individuals[1]['id']: {'roles': ['Matriarch']},
        individuals[3]['id']: {'roles': ['IrritatingGit']},
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
            'members', {individuals[2]['id']: {'roles': ['Matriarch']}}
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
            {'4037': {'roles': ['Matriarch']}},
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
    assert group_data.json['members'][individuals[2]['id']]['roles'] == ['Matriarch']

    patch_make_irritating = [
        test_utils.patch_replace_op(
            'members',
            {individuals[2]['id']: {'roles': ['Matriarch', 'IrritatingGit']}},
        )
    ]
    soc_group_utils.patch_social_group(
        flask_app_client, researcher_1, group_guid, patch_make_irritating
    )

    group_data = soc_group_utils.read_social_group(
        flask_app_client, researcher_1, group_guid
    )
    assert group_data.json['members'][individuals[2]['id']]['roles'] == [
        'Matriarch',
        'IrritatingGit',
    ]


@pytest.mark.skipif(
    module_unavailable('social_groups'), reason='SocialGroup module disabled'
)
def test_individual_delete(
    db, flask_app_client, researcher_1, admin_user, request, test_root
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user, request)

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
            individuals[0]['id']: {'roles': ['Matriarch']},
            individuals[1]['id']: {},
            individuals[2]['id']: {'roles': ['IrritatingGit']},
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
