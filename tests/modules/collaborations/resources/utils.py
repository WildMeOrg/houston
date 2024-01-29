# -*- coding: utf-8 -*-
"""
Collaboration resources utils
-------------
"""
import json

from tests import utils as test_utils

PATH = '/api/v1/collaborations/'


def get_collab_object_for_user(user, collab_guid, expected_len=1):
    user_assocs = [
        assoc
        for assoc in user.get_collaboration_associations()
        if str(assoc.collaboration_guid) == collab_guid
    ]
    assert len(user_assocs) == expected_len

    return user_assocs[0].collaboration if expected_len > 0 else None


def create_collaboration(
    flask_app_client, user, data, expected_status_code=200, expected_error=''
):
    if user:
        with flask_app_client.login(user, auth_scopes=('collaborations:write',)):
            response = flask_app_client.post(
                '%s' % PATH,
                content_type='application/json',
                data=json.dumps(data),
            )
    else:
        response = flask_app_client.post(
            '%s' % PATH,
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'members'})
    elif 400 <= expected_status_code < 500:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
        assert response.json['message'] == expected_error, response.json['message']
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_collaboration(
    flask_app_client,
    collaboration_guid,
    user,
    data,
    expected_status_code=200,
    expected_error=None,
):
    return test_utils.patch_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:write',
        path=f'{PATH}{collaboration_guid}',
        data=data,
        response_200={'guid'},
        expected_status_code=expected_status_code,
        expected_error=expected_error,
    )


def read_collaboration(
    flask_app_client, user, collaboration_guid, expected_status_code=200
):
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:read',
        path=f'{PATH}{collaboration_guid}',
        expected_status_code=expected_status_code,
        response_200={'members', 'guid'},
    )


def read_all_collaborations(
    flask_app_client,
    user,
    expected_status_code=200,
):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:read',
        path=PATH,
        expected_status_code=expected_status_code,
        expected_fields={'members', 'guid'},
    )


def request_export(
    flask_app_client,
    collaboration_guid,
    user,
    expected_status_code=200,
    expected_error=None,
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:write',
        path=f'{PATH}export_request/{collaboration_guid}',
        data={},
        expected_status_code=expected_status_code,
        response_200={'guid'},
        expected_error=expected_error,
    )


def request_edit(
    flask_app_client,
    collaboration_guid,
    user,
    expected_status_code=200,
    expected_error=None,
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='collaborations:write',
        path=f'{PATH}edit_request/{collaboration_guid}',
        data={},
        expected_status_code=expected_status_code,
        response_200={'guid'},
        expected_error=expected_error,
    )


def validate_expected_states(json_data, expected_states):
    # Check collab is in the state we expect
    members = json_data.get('members')
    assert members
    assert len(members) == len(expected_states)
    for expected_user_guid in expected_states.keys():
        for expected_state in expected_states[expected_user_guid].keys():
            assert (
                members[str(expected_user_guid)][expected_state]
                == expected_states[expected_user_guid][expected_state]
            )


def validate_user_access(requesting_user, collab_guid, user_access):
    collab = get_collab_object_for_user(requesting_user, collab_guid)
    for user_guid in user_access:
        assert collab.user_has_read_access(user_guid) == user_access[user_guid]['view']
        assert (
            collab.user_has_export_access(user_guid) == user_access[user_guid]['export']
        )
        assert collab.user_has_edit_access(user_guid) == user_access[user_guid]['edit']


def validate_no_access(collab_guid, user_1, user_2):
    expected_access = {
        user_1.guid: {'view': False, 'export': False, 'edit': False},
        user_2.guid: {'view': False, 'export': False, 'edit': False},
    }
    validate_user_access(user_1, collab_guid, expected_access)


def validate_read_only(collab_guid, user_1, user_2):
    expected_access = {
        user_1.guid: {'view': True, 'export': False, 'edit': False},
        user_2.guid: {'view': True, 'export': False, 'edit': False},
    }
    validate_user_access(user_1, collab_guid, expected_access)


def validate_export_access(collab_guid, user_1, user_2):
    expected_access = {
        user_1.guid: {'view': True, 'export': True, 'edit': False},
        user_2.guid: {'view': True, 'export': True, 'edit': False},
    }
    validate_user_access(user_1, collab_guid, expected_access)


def validate_full_access(collab_guid, user_1, user_2):
    expected_access = {
        user_1.guid: {'view': True, 'export': True, 'edit': True},
        user_2.guid: {'view': True, 'export': True, 'edit': True},
    }
    validate_user_access(user_1, collab_guid, expected_access)


def create_simple_collaboration(flask_app_client, requesting_user, other_user):
    data = {'user_guid': str(other_user.guid)}
    create_resp = create_collaboration(flask_app_client, requesting_user, data)
    expected_states = {
        requesting_user.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
        other_user.guid: {'viewState': 'pending', 'editState': 'not_initiated'},
    }
    validate_expected_states(create_resp.json, expected_states)
    validate_no_access(create_resp.json['guid'], requesting_user, other_user)

    return create_resp


def create_simple_manager_collaboration(
    flask_app_client, user_manager, first_user, second_user
):
    data = {'user_guid': str(first_user.guid), 'second_user_guid': str(second_user.guid)}
    create_resp = create_collaboration(flask_app_client, user_manager, data)
    expected_states = {
        first_user.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
        second_user.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
    }
    validate_expected_states(create_resp.json, expected_states)
    validate_read_only(create_resp.json['guid'], first_user, second_user)
    return create_resp


def approve_view_on_collaboration(
    flask_app_client, collab_guid, approving_user, other_user
):
    patch_data = [test_utils.patch_replace_op('view_permission', 'approved')]

    patch_resp = patch_collaboration(
        flask_app_client,
        collab_guid,
        approving_user,
        patch_data,
    )
    expected_states = {
        approving_user.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
        other_user.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
    }
    validate_expected_states(patch_resp.json, expected_states)
    validate_read_only(collab_guid, approving_user, other_user)

    return patch_resp


def deny_view_on_collaboration(flask_app_client, collab_guid, approving_user, other_user):
    patch_data = [test_utils.patch_replace_op('view_permission', 'denied')]

    patch_resp = patch_collaboration(
        flask_app_client,
        collab_guid,
        approving_user,
        patch_data,
    )
    expected_states = {
        approving_user.guid: {'viewState': 'denied', 'editState': 'not_initiated'},
        other_user.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
    }
    validate_expected_states(patch_resp.json, expected_states)

    return patch_resp


def request_export_simple_collaboration(
    flask_app_client, collab_guid, requesting_user, other_user
):
    export_resp = request_export(flask_app_client, collab_guid, requesting_user)
    expected_states = {
        requesting_user.guid: {
            'viewState': 'approved',
            'exportState': 'approved',
            'editState': 'not_initiated',
        },
        other_user.guid: {
            'viewState': 'approved',
            'exportState': 'pending',
            'editState': 'not_initiated',
        },
    }
    validate_expected_states(export_resp.json, expected_states)
    validate_read_only(collab_guid, requesting_user, other_user)

    return export_resp


def approve_export_on_collaboration(
    flask_app_client, collab_guid, approving_user, other_user
):
    patch_data = [test_utils.patch_replace_op('export_permission', 'approved')]

    patch_resp = patch_collaboration(
        flask_app_client,
        collab_guid,
        approving_user,
        patch_data,
    )
    expected_states = {
        approving_user.guid: {
            'viewState': 'approved',
            'exportState': 'approved',
            'editState': 'not_initiated',
        },
        other_user.guid: {
            'viewState': 'approved',
            'exportState': 'approved',
            'editState': 'not_initiated',
        },
    }
    validate_expected_states(patch_resp.json, expected_states)
    validate_export_access(collab_guid, approving_user, other_user)

    return patch_resp


def request_edit_simple_collaboration(
    flask_app_client, collab_guid, requesting_user, other_user
):
    edit_resp = request_edit(flask_app_client, collab_guid, requesting_user)
    expected_states = {
        requesting_user.guid: {
            'viewState': 'approved',
            'exportState': 'approved',
            'editState': 'approved',
        },
        other_user.guid: {
            'viewState': 'approved',
            'exportState': 'approved',
            'editState': 'pending',
        },
    }
    validate_expected_states(edit_resp.json, expected_states)
    validate_export_access(collab_guid, requesting_user, other_user)

    return edit_resp


def approve_edit_on_collaboration(
    flask_app_client, collab_guid, approving_user, other_user
):
    patch_data = [test_utils.patch_replace_op('edit_permission', 'approved')]

    patch_resp = patch_collaboration(
        flask_app_client,
        collab_guid,
        approving_user,
        patch_data,
    )
    expected_states = {
        approving_user.guid: {
            'viewState': 'approved',
            'exportState': 'approved',
            'editState': 'approved',
        },
        other_user.guid: {
            'viewState': 'approved',
            'exportState': 'approved',
            'editState': 'approved',
        },
    }
    validate_expected_states(patch_resp.json, expected_states)
    validate_full_access(collab_guid, approving_user, other_user)

    return patch_resp


def revoke_edit_on_collaboration(
    flask_app_client, collab_guid, revoking_user, other_user
):
    patch_data = [test_utils.patch_replace_op('edit_permission', 'revoked')]

    patch_resp = patch_collaboration(
        flask_app_client,
        collab_guid,
        revoking_user,
        patch_data,
    )
    expected_states = {
        revoking_user.guid: {'viewState': 'approved', 'editState': 'revoked'},
        other_user.guid: {'viewState': 'approved', 'editState': 'approved'},
    }
    validate_expected_states(patch_resp.json, expected_states)
    validate_export_access(collab_guid, revoking_user, other_user)

    return patch_resp


def revoke_view_on_collaboration(
    flask_app_client, collab_guid, revoking_user, other_user, was_edit=False
):
    patch_data = [test_utils.patch_replace_op('view_permission', 'revoked')]

    patch_resp = patch_collaboration(
        flask_app_client,
        collab_guid,
        revoking_user,
        patch_data,
    )
    if was_edit:
        expected_states = {
            revoking_user.guid: {'viewState': 'revoked', 'editState': 'revoked'},
            other_user.guid: {'viewState': 'approved', 'editState': 'approved'},
        }
    else:
        expected_states = {
            revoking_user.guid: {'viewState': 'revoked', 'editState': 'not_initiated'},
            other_user.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
        }
    validate_expected_states(patch_resp.json, expected_states)
    validate_no_access(collab_guid, revoking_user, other_user)

    return patch_resp
