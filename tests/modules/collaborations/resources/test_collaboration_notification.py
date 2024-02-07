# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.notifications.resources.utils as notif_utils
import tests.utils as utils
from tests.utils import module_unavailable


# Full sequence, create the collaboration, validate that the notification is received, approve the view aspect
# Request edit, validate that notification is received, approve edit.
@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_edit_collaboration(flask_app_client, researcher_1, researcher_2, db, request):

    # Start with nothing outstanding
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_1)
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)

    # Researcher 2 requests to collaborate with researcher1
    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_2, researcher_1
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)

    request.addfinalizer(collab.delete)

    # Check researcher1 gets the notification
    researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1
    )
    collab_requests_from_res2 = notif_utils.get_unread_notifications(
        researcher_1_notifs.json, str(researcher_2.guid), 'collaboration_request'
    )
    assert len(collab_requests_from_res2) >= 1

    # Researcher 1 tries to upgrade to Edit without approving, should fail
    resp_msg = 'Unable to start edit on unapproved collaboration'
    collab_utils.request_edit(flask_app_client, collab.guid, researcher_1, 400, resp_msg)

    # patch to approve collaboration by researcher1
    collab_utils.approve_view_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )

    # Researcher 1 requests/approves that this is escalated to an export collaboration (middle step)
    collab_utils.request_export_simple_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )
    collab_utils.approve_export_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # Researcher 2 should now receive a notification
    researcher_2_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    collab_edit_approvals_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, str(researcher_1.guid), 'collaboration_approved'
    )
    assert len(collab_edit_approvals_from_res1) == 1
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)

    # Researcher 1 requests that this is escalated to an edit collaboration
    collab_utils.request_edit_simple_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )

    # Researcher 2 should now receive a notification
    researcher_2_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    collab_edit_requests_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, str(researcher_1.guid), 'collaboration_edit_request'
    )
    assert len(collab_edit_requests_from_res1) == 1
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)

    # patch to approve edit collaboration by researcher2
    collab_utils.approve_edit_on_collaboration(
        flask_app_client, collab_guid, researcher_2, researcher_1
    )

    # Researcher 1 should be told about this
    researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1
    )
    edit_approvals_from_res2 = notif_utils.get_unread_notifications(
        researcher_1_notifs.json, str(researcher_2.guid), 'collaboration_request'
    )
    assert len(edit_approvals_from_res2) >= 1

    # back to view only
    collab_utils.revoke_edit_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )

    # researcher 2 should get a notification
    researcher_2_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    collab_edit_revokes_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, str(researcher_1.guid), 'collaboration_edit_revoke'
    )
    assert len(collab_edit_revokes_from_res1) == 1
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)

    # Researcher 1 can change their mind and go straight back to edit
    collab_utils.request_edit(flask_app_client, collab.guid, researcher_1)
    collab_utils.validate_full_access(collab_guid, researcher_1, researcher_2)

    researcher_2_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    assert len(researcher_2_notifs.json) == 0

    # remove all permissions
    collab_utils.revoke_view_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2, was_edit=True
    )

    # researcher 2 should get a notification
    researcher_2_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    collab_revokes_from_res1 = notif_utils.get_unread_notifications(
        researcher_2_notifs.json, str(researcher_1.guid), 'collaboration_revoke'
    )
    assert len(collab_revokes_from_res1) == 1


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_multi_collaboration(
    flask_app_client,
    researcher_1,
    researcher_2,
    collab_user_a,
    collab_user_b,
    user_manager_user,
    db,
    request,
):

    # Start with nothing outstanding
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_1)
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)
    notif_utils.mark_all_notifications_as_read(flask_app_client, collab_user_a)
    notif_utils.mark_all_notifications_as_read(flask_app_client, collab_user_b)

    # Everybody requests to collaborate with researcher1
    collabs = []
    for user in researcher_2, collab_user_a, collab_user_b:
        create_resp = collab_utils.create_simple_manager_collaboration(
            flask_app_client, user_manager_user, user, researcher_1
        )
        collab_guid = create_resp.json['guid']
        collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)

        request.addfinalizer(collab.delete)
        collabs.append(collab)

    # Check researcher1 gets the notification
    researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1
    )
    notifs_manager = notif_utils.read_all_notifications(
        flask_app_client, user_manager_user, 'all_unread'
    )

    # Manager should see all 6 notifications, researcher1 should only see those for themselves
    assert len(researcher_1_notifs.json) == 3
    assert len(notifs_manager.json) == 6


@pytest.mark.skipif(
    module_unavailable('collaborations'), reason='Collaborations module disabled'
)
def test_notification_resolution(
    db, flask_app_client, researcher_1, researcher_2, user_manager_user, request
):
    from app.modules.collaborations.models import Collaboration

    # Start with no unread notifications to ensure that they are always created here
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_1)
    notif_utils.mark_all_notifications_as_read(flask_app_client, researcher_2)
    notif_utils.mark_all_notifications_as_read(flask_app_client, user_manager_user)

    members = [researcher_1, researcher_2]
    basic_collab = Collaboration(members, researcher_1)
    request.addfinalizer(basic_collab.delete)

    researcher_2_unread_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    notif_guid = researcher_2_unread_notifs.json[-1]['guid']
    notif_utils.mark_notification_as_read(flask_app_client, researcher_2, notif_guid)

    collab_request_notif = notif_utils.read_notification(
        flask_app_client, researcher_2, notif_guid
    )
    assert collab_request_notif.json['is_read']
    assert not collab_request_notif.json['is_resolved']

    basic_collab.set_approval_state_for_user(researcher_2.guid, 'approved')

    # now that it's approved, the initial request should be resolved.
    collab_request_notif = notif_utils.read_notification(
        flask_app_client, researcher_2, notif_guid
    )
    assert collab_request_notif.json['is_resolved']

    # Now validate that the manager can revoke it for one user and both users get the Notification
    patch_data = [
        utils.patch_replace_op(
            'managed_view_permission',
            {
                'user_guid': str(researcher_2.guid),
                'permission': 'revoked',
            },
        )
    ]
    collab_guid = str(basic_collab.guid)
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, user_manager_user, patch_data
    )
    res1_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_1
    ).json
    res2_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    ).json
    res1_mgr_revokes = [
        msg
        for msg in res1_notifs
        if msg['message_type'] == 'collaboration_manager_revoke'
    ]
    res2_mgr_revokes = [
        msg
        for msg in res2_notifs
        if msg['message_type'] == 'collaboration_manager_revoke'
    ]
    assert len(res1_mgr_revokes) == 1
    assert len(res2_mgr_revokes) == 1
