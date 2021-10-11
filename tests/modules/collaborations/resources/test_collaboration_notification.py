# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.notifications.resources.utils as notif_utils
from tests import utils as test_utils


# Full sequence, create the collaboration, validate that the notification is received, approve the view aspect
# Request edit, validate that notification is received, approve edit.
def test_edit_collaboration(flask_app_client, researcher_1, researcher_2, db, request):

    create_resp = collab_utils.create_simple_collaboration(
        flask_app_client, researcher_2, researcher_1
    )
    collab_guid = create_resp.json['guid']
    collab = collab_utils.get_collab_object_for_user(researcher_1, collab_guid)

    request.addfinalizer(lambda: collab.delete())

    # Check researcher1 gets the notification
    researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1
    )
    collab_requests_from_res2 = notif_utils.get_notifications(
        researcher_1_notifs.json, str(researcher_2.guid), 'collaboration_request'
    )
    assert len(collab_requests_from_res2) >= 1

    # Researcher 1 tries to upgrade to Edit without approving, should fail
    resp_msg = 'Unable to start edit on unapproved collaboration'
    collab_utils.request_edit(flask_app_client, collab.guid, researcher_1, 400, resp_msg)

    # patch to approve collaboration by researcher1
    patch_resp = collab_utils.patch_collaboration(
        flask_app_client,
        collab.guid,
        researcher_1,
        [test_utils.patch_replace_op('view_permission', 'approved')],
    )
    expected_resp = {
        researcher_1.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
        researcher_2.guid: {'viewState': 'approved', 'editState': 'not_initiated'},
    }
    collab_utils.validate_expected_states(patch_resp.json, expected_resp)

    # Researcher 1 requests that this is escalated to an edit collaboration
    collab_utils.request_edit_simple_collaboration(
        flask_app_client, researcher_1, researcher_2
    )

    # Researcher 2 should now receive a notification
    researcher_2_notifs = notif_utils.read_all_unread_notifications(
        flask_app_client, researcher_2
    )
    collab_edit_requests_from_res1 = notif_utils.get_notifications(
        researcher_2_notifs.json, str(researcher_1.guid), 'collaboration_edit_request'
    )
    assert len(collab_edit_requests_from_res1) == 1

    # patch to approve edit collaboration by researcher2
    collab_utils.approve_edit_on_collaboration(
        flask_app_client, researcher_2, researcher_1
    )

    # back to view only TBD move to a separate test, Looks like it's duplicated in patch test
    patch_resp = collab_utils.patch_collaboration(
        flask_app_client,
        collab.guid,
        researcher_1,
        [test_utils.patch_replace_op('edit_permission', 'revoked')],
    )
    expected_resp = {
        researcher_1.guid: {'viewState': 'approved', 'editState': 'revoked'},
        researcher_2.guid: {'viewState': 'approved', 'editState': 'approved'},
    }
    collab_utils.validate_expected_states(patch_resp.json, expected_resp)

    # Researcher 1 can change their mind and go straight back to edit
    edit_response = collab_utils.request_edit(flask_app_client, collab.guid, researcher_1)
    expected_resp = {
        researcher_1.guid: {'viewState': 'approved', 'editState': 'approved'},
        researcher_2.guid: {'viewState': 'approved', 'editState': 'approved'},
    }
    collab_utils.validate_expected_states(edit_response.json, expected_resp)
