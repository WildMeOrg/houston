# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
import tests.modules.notifications.resources.utils as notif_utils
from tests import utils as test_utils


# Full sequence, create the collaboration, validate that the notification is received, approve the view aspect
# Request edit, validate that notification is received, approve edit.
def test_edit_collaboration(flask_app_client, researcher_1, researcher_2, db, request):

    create_data = {'user_guid': str(researcher_1.guid)}
    collab_utils.create_collaboration(flask_app_client, researcher_2, create_data)
    researcher_1_assocs = [
        assoc for assoc in researcher_1.user_collaboration_associations
    ]
    collab = researcher_1_assocs[0].collaboration

    request.addfinalizer(collab.delete)

    # Check collab is in the state we expect
    collab_data = collab_utils.read_collaboration(
        flask_app_client, researcher_1, collab.guid
    )
    members = collab_data.json.get('members')
    assert members
    assert members[str(researcher_1.guid)]['viewState'] == 'pending'
    assert members[str(researcher_1.guid)]['editState'] == 'not_initiated'
    assert members[str(researcher_2.guid)]['viewState'] == 'approved'
    assert members[str(researcher_2.guid)]['editState'] == 'not_initiated'

    # Check researcher1 gets the notification
    researcher_1_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_1
    )
    collab_requests_from_res2 = notif_utils.get_notifications(
        researcher_1_notifs.json, researcher_2.email, 'collaboration_request'
    )
    assert len(collab_requests_from_res2) >= 1

    # Researcher 1 tries to upgrade to Edit without approving, should fail
    resp_msg = 'Unable to start edit on unapproved collaboration'
    collab_utils.request_edit(flask_app_client, collab.guid, researcher_1, 400, resp_msg)

    # patch to approve collaboration by researcher1
    patch_data = [test_utils.patch_replace_op('view_permission', 'approved')]

    collab_utils.patch_collaboration(
        flask_app_client, collab.guid, researcher_1, patch_data
    )

    # Check collab is in the state we expect (as researcher 2 for variation)
    collab_data = collab_utils.read_collaboration(
        flask_app_client, researcher_2, collab.guid
    )
    members = collab_data.json.get('members')
    assert members
    assert members[str(researcher_1.guid)]['viewState'] == 'approved'
    assert members[str(researcher_1.guid)]['editState'] == 'not_initiated'
    assert members[str(researcher_2.guid)]['viewState'] == 'approved'
    assert members[str(researcher_2.guid)]['editState'] == 'not_initiated'

    # Researcher 1 requests that this is escalated to an edit collaboration
    collab_utils.request_edit(flask_app_client, collab.guid, researcher_1)

    # Check collab is in the state we expect
    collab_data = collab_utils.read_collaboration(
        flask_app_client, researcher_1, collab.guid
    )
    members = collab_data.json.get('members')
    assert members
    assert members[str(researcher_1.guid)]['viewState'] == 'approved'
    assert members[str(researcher_1.guid)]['editState'] == 'approved'
    assert members[str(researcher_2.guid)]['viewState'] == 'approved'
    assert members[str(researcher_2.guid)]['editState'] == 'pending'

    # Researcher 2 should now receive a notification
    researcher_2_notifs = notif_utils.read_all_notifications(
        flask_app_client, researcher_2
    )
    collab_edit_requests_from_res1 = notif_utils.get_notifications(
        researcher_2_notifs.json, researcher_1.email, 'collaboration_edit_request'
    )
    assert len(collab_edit_requests_from_res1) == 1

    # patch to approve edit collaboration by researcher2
    patch_data = [test_utils.patch_replace_op('edit_permission', 'approved')]

    collab_utils.patch_collaboration(
        flask_app_client, collab.guid, researcher_2, patch_data
    )

    # Check collab is in the state we expect (as researcher 2 for variation)
    collab_data = collab_utils.read_collaboration(
        flask_app_client, researcher_2, collab.guid
    )
    members = collab_data.json.get('members')
    assert members
    assert members[str(researcher_1.guid)]['viewState'] == 'approved'
    assert members[str(researcher_1.guid)]['editState'] == 'approved'
    assert members[str(researcher_2.guid)]['viewState'] == 'approved'
    assert members[str(researcher_2.guid)]['editState'] == 'approved'
