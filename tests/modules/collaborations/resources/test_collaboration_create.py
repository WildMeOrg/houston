# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.users.resources.utils as user_utils
import uuid


# TBD this should go
def validate_collab(resp_json, user_guids, view_approvals):
    members = resp_json.get('members', {})

    user_guids_received = resp_json.get('user_guids', {})
    assert set(user_guids_received) <= set(user_guids)
    assert len(user_guids_received) == 2
    if members:
        for user_guid in user_guids:
            user_guid_str = str(user_guid)
            assert user_guid_str in members.keys()
            assert members[user_guid_str]['viewState'] == view_approvals[user_guid_str]


def test_create_collaboration(
    flask_app_client,
    researcher_1,
    readonly_user,
    researcher_2,
    user_manager_user,
    db,
    request,
):
    create_resp = collab_utils.create_simple_collaboration(researcher_2, readonly_user)
    readonly_user_collab = collab_utils.get_collab_object_for_user(
        readonly_user, create_resp.json['guid']
    )

    request.addfinalizer(lambda: readonly_user_collab.delete())

    collab = None
    try:
        create_resp = collab_utils.create_simple_collaboration(researcher_1, researcher_2)
        collab = collab_utils.get_collab_object_for_user(
            researcher_1, create_resp.json['guid']
        )

        # only user manager should be able to read the list
        collab_utils.read_all_collaborations(flask_app_client, readonly_user, 403)
        collab_utils.read_all_collaborations(flask_app_client, researcher_1, 403)
        all_resp = collab_utils.read_all_collaborations(
            flask_app_client, user_manager_user
        )

        # which should contain the same Users
        assert len(all_resp.json) == 2
        assert set(all_resp.json[0]['user_guids']) == set(
            {str(readonly_user.guid), str(researcher_2.guid)}
        )

        user_resp = user_utils.read_user(flask_app_client, researcher_1, 'me')
        assert 'collaborations' in user_resp.json.keys()
        assert len(user_resp.json['collaborations']) == 1
        expected_states = {
            researcher_1.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
            researcher_2.guid: {'viewState': 'pending', 'editState': 'not_initiated'},
        }
        collab_utils.validate_expected_states(
            user_resp.json['collaborations'][0], expected_states
        )

    finally:
        if collab:
            collab.delete()


# TBD not sure if this is ripe for refactoring
def test_create_approved_collaboration(
    flask_app_client, researcher_1, researcher_2, user_manager_user, readonly_user, db
):

    duff_uuid = str(uuid.uuid4())
    data = {
        'user_guid': str(researcher_1.guid),
        'second_user_guid': duff_uuid,
    }
    resp_msg = f'Second user with guid {duff_uuid} not found'
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


def test_create_repeat_collaboration(
    flask_app_client,
    researcher_1,
    readonly_user,
    researcher_2,
    user_manager_user,
    db,
    request,
):
    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)
    request.addfinalizer(lambda: collab.delete())

    # Should return the first one again
    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    assert create_resp.json['guid'] == collab_guid
