# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
from tests import utils
import pytest

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
    resp = 'unable to set /view_permission to ambivalence'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
    )

    # Should work
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

    # remove edit only
    collab_utils.revoke_edit_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2
    )

    # remove all permissions
    collab_utils.revoke_view_on_collaboration(
        flask_app_client, collab_guid, researcher_1, researcher_2, was_edit=True
    )


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
    patch_data = [utils.patch_replace_op('view_permission', 'creator')]
    resp = 'unable to set /view_permission to creator'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
    )
    collab_utils.validate_no_access(collab_guid, researcher_1, researcher_2)

    # also should not
    patch_data = [utils.patch_replace_op('view_permission', 'ambivalence')]
    resp = 'unable to set /view_permission to ambivalence'
    collab_utils.patch_collaboration(
        flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
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

    patch_data = [utils.patch_replace_op('view_permission', 'declined')]
    resp = 'unable to set /view_permission to declined'
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
