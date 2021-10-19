# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import tests.modules.social_groups.resources.utils as soc_group_utils
import tests.modules.individuals.resources.utils as individual_utils
import tests.modules.audit_logs.resources.utils as audit_utils

log = logging.getLogger(__name__)


def test_basic_operation(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request
):
    # Set the basic roles we want
    soc_group_utils.set_basic_roles(flask_app_client, admin_user)

    # Create a few individuals to use
    matriarch = individual_utils.create_individual(
        flask_app_client,
        researcher_1,
        data_in=individual_utils.generate_individual_encounter_data(
            researcher_1, db, request
        ),
    )
    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, researcher_1, matriarch.json['result']['id']
        )
    )
    other_member_1 = individual_utils.create_individual(
        flask_app_client,
        researcher_1,
        data_in=individual_utils.generate_individual_encounter_data(
            researcher_1, db, request
        ),
    )
    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, researcher_1, other_member_1.json['result']['id']
        )
    )
    other_member_2 = individual_utils.create_individual(
        flask_app_client,
        researcher_1,
        data_in=individual_utils.generate_individual_encounter_data(
            researcher_1, db, request
        ),
    )
    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, researcher_1, other_member_2.json['result']['id']
        )
    )
    # Create a social group for them
    data = {
        'name': 'Disreputable bunch of hooligans',
        'members': {
            matriarch.json['result']['id']: {'role': 'Matriarch'},
            other_member_1.json['result']['id']: {},
            other_member_2.json['result']['id']: {'role': 'IrritatingGit'},
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


def test_error_creation(
    db, flask_app_client, researcher_1, researcher_2, admin_user, request
):
    # TODO bunch of failure legs

    pass
