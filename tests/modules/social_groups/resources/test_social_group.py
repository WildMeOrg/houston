# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging
import uuid

import tests.modules.social_groups.resources.utils as soc_group_utils
import tests.modules.individuals.resources.utils as individual_utils
import tests.modules.audit_logs.resources.utils as audit_utils
import json

log = logging.getLogger(__name__)


def test_basic_operation(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user)

    # Create some individuals to use in testing
    matriarch = individual_utils.create_individual_with_encounter(
        db, flask_app_client, researcher_1, request
    )
    other_member_1 = individual_utils.create_individual_with_encounter(
        db, flask_app_client, researcher_1, request
    )
    other_member_2 = individual_utils.create_individual_with_encounter(
        db, flask_app_client, researcher_1, request
    )

    # Create a social group for them
    data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            matriarch['id']: {'role': 'Matriarch'},
            other_member_1['id']: {},
            other_member_2['id']: {'role': 'IrritatingGit'},
        },
    }
    group_resp = soc_group_utils.create_social_group(flask_app_client, researcher_1, data)
    group_guid = group_resp.json['guid']
    request.addfinalizer(
        lambda: soc_group_utils.delete_social_group(
            flask_app_client, researcher_1, group_guid
        )
    )

    # read it
    soc_group_utils.read_social_group(flask_app_client, researcher_1, group_guid)
    group_as_res_2 = soc_group_utils.read_social_group(
        flask_app_client, researcher_2, group_guid
    )
    assert group_as_res_2.json['name'] == data['name']
    for member_guid in data['members']:
        assert member_guid in group_as_res_2.json['members']
        if 'role' in data['members'][member_guid]:
            assert (
                group_as_res_2.json['members'][member_guid]['role']
                == data['members'][member_guid]['role']
            )
        else:
            assert group_as_res_2.json['members'][member_guid]['role'] is None

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
def test_error_config(flask_app_client, researcher_1, admin_user):
    valid_data = {
        'key': 'social_group_roles',
        'string': json.dumps(
            {
                'Matriarch': {'multipleInGroup': False},
                'IrritatingGit': {'multipleInGroup': True},
            }
        ),
    }

    # Valid data but non admin user so should fail
    error = "You don't have the permission to access the requested resource."
    soc_group_utils.set_roles(flask_app_client, researcher_1, valid_data, 403, error)

    missing_field = {
        'key': 'social_group_roles',
        'string': json.dumps(
            {
                'Matriarch': {},
                'IrritatingGit': {'multipleInGroup': True},
            }
        ),
    }
    error = "Role dictionary must have the following keys : {'multipleInGroup'}"
    soc_group_utils.set_roles(flask_app_client, admin_user, missing_field, 400, error)

    extra_field = {
        'key': 'social_group_roles',
        'string': json.dumps(
            {
                'Matriarch': {'multipleInGroup': False, 'attitude': True},
                'IrritatingGit': {'multipleInGroup': True},
            }
        ),
    }
    soc_group_utils.set_roles(flask_app_client, admin_user, extra_field, 400, error)


def test_invalid_creation(
    db, flask_app_client, researcher_1, researcher_2, admin_user, collab_user_a, request
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user)

    # Create some individuals to use in testing
    matriarch = individual_utils.create_individual_with_encounter(
        db, flask_app_client, researcher_1, request
    )
    other_member_1 = individual_utils.create_individual_with_encounter(
        db, flask_app_client, researcher_1, request
    )
    other_member_2 = individual_utils.create_individual_with_encounter(
        db, flask_app_client, researcher_1, request
    )

    valid_data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            matriarch['id']: {'role': 'Matriarch'},
            other_member_1['id']: {},
            other_member_2['id']: {'role': 'IrritatingGit'},
        },
    }
    # Shouldn't work with anon user
    error = (
        'The server could not verify that you are authorized to access the URL requested. You either supplied '
        "the wrong credentials (e.g. a bad password), or your browser doesn't understand how to supply the "
        'credentials required.'
    )
    soc_group_utils.create_social_group(flask_app_client, None, valid_data, 401, error)

    # or collaborator
    error = "You don't have the permission to access the requested resource."
    soc_group_utils.create_social_group(
        flask_app_client, collab_user_a, valid_data, 403, error
    )

    # or researcher without read permission
    error = f"Social Group member { matriarch['id']} not accessible by user"
    soc_group_utils.create_social_group(
        flask_app_client, researcher_2, valid_data, 400, error
    )

    missing_name = {
        'members': {
            matriarch['id']: {'role': 'Matriarch'},
            other_member_1['id']: {},
            other_member_2['id']: {'role': 'IrritatingGit'},
        },
    }
    error = 'The request was well-formed but was unable to be followed due to semantic errors.'
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, missing_name, 422, error
    )

    invalid_fields = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            matriarch['id']: {'role': 'Matriarch'},
            other_member_1['id']: {'attitude': 'Stubborn'},
            other_member_2['id']: {'role': 'IrritatingGit'},
        },
    }
    error = (
        f"Social Group member {other_member_1['id']} fields not supported {{'attitude'}}"
    )
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, invalid_fields, 400, error
    )

    random_guid = str(uuid.uuid4())
    invalid_guid = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            random_guid: {'role': 'Matriarch'},
            other_member_1['id']: {},
            other_member_2['id']: {'role': 'IrritatingGit'},
        },
    }
    error = f'Social Group member {random_guid} does not match an individual'
    soc_group_utils.create_social_group(
        flask_app_client, researcher_1, invalid_guid, 400, error
    )
