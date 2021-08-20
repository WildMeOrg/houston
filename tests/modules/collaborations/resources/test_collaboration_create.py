# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.users.resources.utils as user_utils
import uuid


def validate_collab(resp_json, user_guids, view_approvals):
    members = resp_json.get('members', {})
    assert len(members) == len(user_guids)
    for user_guid in user_guids:
        user_guid_str = str(user_guid)
        assert user_guid_str in members.keys()
        assert members[user_guid_str]['viewState'] == view_approvals[user_guid_str]


def test_create_collaboration(
    flask_app_client, researcher_1, readonly_user, researcher_2, user_manager_user, db
):
    data = {'user_guid': str(readonly_user.guid)}
    resp_msg = f'User with guid {readonly_user.guid} is not a researcher'
    collab_utils.create_collaboration(flask_app_client, researcher_1, data, 400, resp_msg)

    collab = None
    try:
        data = {'user_guid': str(researcher_2.guid)}
        resp = collab_utils.create_collaboration(flask_app_client, researcher_1, data)
        researcher_1_assocs = [
            assoc for assoc in researcher_1.user_collaboration_associations
        ]
        collab = researcher_1_assocs[0].collaboration
        assert len(researcher_1_assocs) == 1
        expected_users = [str(researcher_1.guid), str(researcher_2.guid)]
        expected_states = {
            str(researcher_1.guid): 'approved',
            str(researcher_2.guid): 'pending',
        }
        validate_collab(resp.json, expected_users, expected_states)

        # only user manager should be able to read the list
        collab_utils.read_all_collaborations(flask_app_client, readonly_user, 403)
        collab_utils.read_all_collaborations(flask_app_client, researcher_1, 403)
        all_resp = collab_utils.read_all_collaborations(
            flask_app_client, user_manager_user
        )

        # which should contain the same data
        assert len(all_resp.json) == 1
        validate_collab(all_resp.json[0], expected_users, expected_states)

        user_resp = user_utils.read_user(flask_app_client, researcher_1, 'me')
        assert 'collaborations' in user_resp.json.keys()
        assert len(user_resp.json['collaborations']) == 1
        validate_collab(
            user_resp.json['collaborations'][0], expected_users, expected_states
        )

    finally:
        if collab:
            collab.delete()


def test_create_approved_collaboration(
    flask_app_client, researcher_1, researcher_2, user_manager_user, readonly_user, db
):
    # couple of failure checks
    data = {
        'user_guid': str(researcher_2.guid),
        'second_user_guid': str(readonly_user.guid),
    }
    resp_msg = f'User with guid {readonly_user.guid} is not a researcher'
    collab_utils.create_collaboration(
        flask_app_client, user_manager_user, data, 400, resp_msg
    )

    duff_uuid = str(uuid.uuid4())
    data = {
        'user_guid': str(researcher_1.guid),
        'second_user_guid': duff_uuid,
    }
    resp_msg = f'User with guid {duff_uuid} not found'
    collab_utils.create_collaboration(
        flask_app_client, user_manager_user, data, 400, resp_msg
    )

    # valid one
    data = {
        'user_guid': str(researcher_1.guid),
        'second_user_guid': str(readonly_user.guid),
    }
    resp_msg = f'User with guid {readonly_user.guid} is not a researcher'
    collab_utils.create_collaboration(
        flask_app_client, user_manager_user, data, 400, resp_msg
    )

    data = {
        'user_guid': str(researcher_1.guid),
        'second_user_guid': str(researcher_2.guid),
    }

    collab = None
    try:
        resp = collab_utils.create_collaboration(
            flask_app_client, user_manager_user, data
        )
        researcher_1_assocs = [
            assoc for assoc in researcher_1.user_collaboration_associations
        ]
        collab = researcher_1_assocs[0].collaboration
        assert len(researcher_1_assocs) == 1
        expected_users = [
            str(researcher_1.guid),
            str(researcher_2.guid),
            str(user_manager_user.guid),
        ]
        expected_states = {
            str(researcher_1.guid): 'approved',
            str(researcher_2.guid): 'approved',
            str(user_manager_user.guid): 'creator',
        }
        validate_collab(resp.json, expected_users, expected_states)

    finally:
        if collab:
            collab.delete()
