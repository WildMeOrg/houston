# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
from tests import utils


def test_patch_collaboration(flask_app_client, researcher_1, researcher_2, db):
    from app.modules.collaborations.models import Collaboration

    collab = None
    try:
        data = {'user_guid': str(researcher_2.guid)}
        collab_utils.create_collaboration(flask_app_client, researcher_1, data)
        collabs = Collaboration.query.all()
        collab = collabs[0]
        collab_guid = collab.guid
        assert not collab.user_has_read_access(researcher_1.guid)
        assert not collab.user_has_edit_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)
        assert collab.user_has_edit_access(researcher_2.guid)

        # should not work
        patch_data = [utils.patch_replace_op('view_permission', 'ambivalence')]
        resp = 'unable to set /view_permission to ambivalence'
        collab_utils.patch_collaboration(
            flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
        )
        patch_data = [utils.patch_replace_op('view_permission', 'approved')]

        collab_utils.patch_collaboration(
            flask_app_client,
            collab_guid,
            researcher_2,
            patch_data,
        )
        assert collab.user_has_read_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)
        assert not collab.user_has_edit_access(researcher_1.guid)
        assert collab.user_has_edit_access(researcher_2.guid)
        patch_data = [utils.patch_replace_op('edit_permission', 'approved')]

        collab_utils.patch_collaboration(
            flask_app_client,
            collab_guid,
            researcher_2,
            patch_data,
        )
        assert collab.user_has_read_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)
        assert collab.user_has_edit_access(researcher_1.guid)
        assert collab.user_has_edit_access(researcher_2.guid)

        patch_data = [utils.patch_replace_op('edit_permission', 'revoked')]
        collab_utils.patch_collaboration(
            flask_app_client,
            collab_guid,
            researcher_1,
            patch_data,
        )
        assert collab.user_has_read_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)
        assert collab.user_has_edit_access(researcher_1.guid)
        assert not collab.user_has_edit_access(researcher_2.guid)

        patch_data = [utils.patch_replace_op('view_permission', 'revoked')]
        collab_utils.patch_collaboration(
            flask_app_client,
            collab_guid,
            researcher_1,
            patch_data,
        )
        assert collab.user_has_read_access(researcher_1.guid)
        assert not collab.user_has_read_access(researcher_2.guid)
        assert collab.user_has_edit_access(researcher_1.guid)
        assert not collab.user_has_edit_access(researcher_2.guid)
    finally:
        if collab:
            collab.delete()


# Tests the approved and not approved state transitions for the collaboration.
# Only on the view as the edit uses exactly the same function
def test_patch_collaboration_states(flask_app_client, researcher_1, researcher_2, db):
    from app.modules.collaborations.models import Collaboration

    collab = None
    try:
        data = {'user_guid': str(researcher_2.guid)}
        collab_utils.create_collaboration(flask_app_client, researcher_1, data)
        collabs = Collaboration.query.all()
        collab = collabs[0]
        collab_guid = collab.guid
        assert not collab.user_has_read_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)

        # should not work
        patch_data = [utils.patch_replace_op('view_permission', 'creator')]
        resp = 'unable to set /view_permission to creator'
        collab_utils.patch_collaboration(
            flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
        )

        # should not
        patch_data = [utils.patch_replace_op('view_permission', 'ambivalence')]
        resp = 'unable to set /view_permission to ambivalence'
        collab_utils.patch_collaboration(
            flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
        )
        patch_data = [utils.patch_replace_op('view_permission', 'approved')]
        collab_utils.patch_collaboration(
            flask_app_client,
            collab_guid,
            researcher_2,
            patch_data,
        )

        patch_data = [utils.patch_replace_op('view_permission', 'pending')]
        resp = 'unable to set /view_permission to pending'
        collab_utils.patch_collaboration(
            flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
        )
        assert collab.user_has_read_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)

        patch_data = [utils.patch_replace_op('view_permission', 'declined')]
        resp = 'unable to set /view_permission to declined'
        collab_utils.patch_collaboration(
            flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
        )
        patch_data = [utils.patch_replace_op('view_permission', 'revoked')]
        collab_utils.patch_collaboration(
            flask_app_client,
            collab_guid,
            researcher_2,
            patch_data,
        )
        assert not collab.user_has_read_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)

        patch_data = [utils.patch_replace_op('view_permission', 'not_initiated')]
        resp = 'unable to set /view_permission to not_initiated'
        collab_utils.patch_collaboration(
            flask_app_client, collab_guid, researcher_2, patch_data, 400, resp
        )
        patch_data = [utils.patch_replace_op('view_permission', 'approved')]
        collab_utils.patch_collaboration(
            flask_app_client,
            collab_guid,
            researcher_2,
            patch_data,
        )
        assert collab.user_has_read_access(researcher_1.guid)
        assert collab.user_has_read_access(researcher_2.guid)
    finally:
        if collab:
            collab.delete()
