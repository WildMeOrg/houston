# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.notifications.resources.utils as notif_utils
from tests import utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_patch_collaboration(flask_app_client, researcher_1, researcher_2, request):

    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)
    request.addfinalizer(collab.delete)

    # should not work
    patch_data = [utils.patch_replace_op('view_permission', 'ambivalence')]
    resp = 'State "ambivalence" not in allowed states: denied, approved, pending, not_initiated, revoked'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 409, resp
    )

    # Should work
    collab_utils.approve_view_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # Researcher 1 requests that this is escalated to an edit collaboration
    #  now (via #950) this should *not* work as we need export first
    resp_msg = 'Unable to start edit on unapproved collaboration'
    collab_utils.request_edit(flask_app_client, collab_guid, researcher_1, 400, resp_msg)

    collab_utils.request_export_simple_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )
    collab_utils.approve_export_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # now an edit should be possible (as export is approved)
    collab_utils.request_edit_simple_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )
    # which is approved
    collab_utils.approve_edit_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # remove edit only
    collab_utils.revoke_edit_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )

    # remove all permissions
    collab_utils.revoke_view_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2, was_edit=True
    )


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_deny_collaboration(flask_app_client, researcher_1, researcher_2, request):
    import tests.modules.notifications.resources.utils as notif_utils

    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)
    request.addfinalizer(collab.delete)

    researcher_2_unread_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    request_notif = researcher_2_unread_notifs.json[-1]
    request_notif_guid = request_notif['guid']
    assert not request_notif['is_resolved']

    # Should work
    collab_utils.deny_view_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )
    request_notif = notif_utils.read_notification(
        flask_app_client, researcher_2, request_notif_guid
    ).json
    assert request_notif['is_resolved']


# As for above but validate that revoking view also revokes edit
@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_view_revoke(flask_app_client, researcher_1, researcher_2, request):
    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)
    request.addfinalizer(collab.delete)

    collab_utils.approve_view_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # Researcher 1 requests that this is escalated to an edit collaboration
    collab_utils.request_edit_simple_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )

    # which is approved
    collab_utils.approve_edit_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # remove all permissions
    collab_utils.revoke_view_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2, was_edit=True
    )


# Tests the approved and not approved state transitions for the collaboration.
# Only on the view as the edit uses exactly the same function
@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_patch_collaboration_states(
    flask_app_client, researcher_1, researcher_2, db, request
):

    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)
    request.addfinalizer(collab.delete)

    # should not work
    patch_data = [utils.patch_replace_op('view_permission', 'not_initiated')]
    resp = 'unable to set /view_permission to not_initiated'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    # also should not
    patch_data = [utils.patch_replace_op('view_permission', 'ambivalence')]
    resp = 'State "ambivalence" not in allowed states: denied, approved, pending, not_initiated, revoked'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 409, resp
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    collab_utils.approve_view_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    patch_data = [utils.patch_replace_op('view_permission', 'pending')]
    resp = 'unable to set /view_permission to pending'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
    )
    collab_utils.validate_read_only(collab_guid, researcher_1, researcher_2)

    patch_data = [utils.patch_replace_op('view_permission', 'denied')]
    resp = 'unable to set /view_permission to denied'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
    )
    collab_utils.validate_read_only(collab_guid, researcher_1, researcher_2)

    collab_utils.revoke_view_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    patch_data = [utils.patch_replace_op('view_permission', 'not_initiated')]
    resp = 'unable to set /view_permission to not_initiated'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    collab_utils.approve_view_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_patch_managed_collaboration_states(
    flask_app_client, researcher_1, researcher_2, user_manager_user, db, request
):
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_1)
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)

    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)
    request.addfinalizer(collab.delete)

    # should not work
    patch_data = [utils.patch_replace_op('managed_view_permission', 'not a dictionary')]
    resp = 'Value for managed_view_permission must be passed as a dictionary'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, user_manager_user, patch_data, 400, resp
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    # No permission field
    patch_data = [utils.patch_replace_op('managed_view_permission', {})]
    resp = 'Value for managed_view_permission must contain a permission field'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, user_manager_user, patch_data, 400, resp
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    # Garbage user guid
    garbage_uuid = str(uuid.uuid4())
    patch_data = [
        utils.patch_replace_op(
            'managed_view_permission',
            {'user_guid': garbage_uuid, 'permission': 'approved'},
        )
    ]
    resp = f'User for {garbage_uuid} not found'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, user_manager_user, patch_data, 400, resp
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    # should actually work
    patch_data = [
        utils.patch_replace_op(
            'managed_view_permission',
            {'user_guid': str(researcher_2.guid), 'permission': 'approved'},
        )
    ]
    collab_utils.patch_collaboration(
        flask_app_client,
        collab_guid,
        user_manager_user,
        patch_data,
    )
    collab_utils.validate_read_only(collab_guid, researcher_1, researcher_2)

    # Manager should also be able to change edit permissions
    patch_data = [
        utils.patch_replace_op(
            'managed_edit_permission',
            {'user_guid': str(researcher_2.guid), 'permission': 'approved'},
        )
    ]
    collab_utils.patch_collaboration(
        flask_app_client,
        collab_guid,
        user_manager_user,
        patch_data,
    )
    collab_utils.validate_read_only(collab_guid, researcher_1, researcher_2)

    # plus revoke the collaboration
    patch_data = [
        utils.patch_replace_op(
            'managed_view_permission',
            {'permission': 'revoked'},
        )
    ]
    collab_utils.patch_collaboration(
        flask_app_client,
        collab_guid,
        user_manager_user,
        patch_data,
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1, 'unread'
    ).json

    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2, 'unread'
    ).json
    researcher_1_manager_edit_approvals = [
        notif
        for notif in researcher_1_notifs
        if notif['message_type'] == 'collaboration_manager_edit_approved'
    ]
    researcher_2_manager_edit_approvals = [
        notif
        for notif in researcher_2_notifs
        if notif['message_type'] == 'collaboration_manager_edit_approved'
    ]
    assert len(researcher_1_manager_edit_approvals) == 1
    assert len(researcher_2_manager_edit_approvals) == 1
    assert 'manager_name' in researcher_1_manager_edit_approvals[0]['message_values']
    assert 'manager_name' in researcher_2_manager_edit_approvals[0]['message_values']
