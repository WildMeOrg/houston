# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.collaborations.resources.utils as collab_utils
import uuid


def test_create_collaboration(
    flask_app_client, researcher_1, readonly_user, researcher_2, user_manager_user, db
):
    duff_uuid = str(uuid.uuid4())
    data = {'user_guid': duff_uuid}
    resp_msg = f'User with guid {duff_uuid} not found'
    collab_utils.create_collaboration(flask_app_client, researcher_1, data, 400, resp_msg)

    data = {'user_guid': str(readonly_user.guid)}
    resp_msg = f'User with guid {readonly_user.guid} is not a researcher'
    collab_utils.create_collaboration(flask_app_client, researcher_1, data, 400, resp_msg)

    from app.modules.collaborations.models import Collaboration

    collab = None
    try:
        data = {'user_guid': str(researcher_2.guid)}
        resp = collab_utils.create_collaboration(flask_app_client, researcher_1, data)
        collabs = Collaboration.query.all()
        collab = collabs[0]
        assert len(collabs) == 1
        assert resp.json['edit_state'] == 'not_initiated'
        assert resp.json['read_state'] == 'pending'
        members = resp.json.get('members', [])
        assert len(members) == 2
        assert str(researcher_1.guid) in members
        assert str(researcher_2.guid) in members
        assert len(collabs) == 1

        # only user manager should be able to read the list
        collab_utils.read_all_collaborations(flask_app_client, readonly_user, 403)
        collab_utils.read_all_collaborations(flask_app_client, researcher_1, 403)
        all_resp = collab_utils.read_all_collaborations(
            flask_app_client, user_manager_user
        )
        assert len(all_resp.json) == 1
        assert all_resp.json[0]['guid'] == resp.json['guid']
    finally:
        if collab:
            collab.delete()


def test_create_approved_collaboration(
    flask_app_client, researcher_1, researcher_2, user_manager_user, db
):
    from app.modules.collaborations.models import Collaboration

    data = {
        'user_guid': str(researcher_1.guid),
        'second_user_guid': str(researcher_2.guid),
    }

    collab = None
    try:
        resp = collab_utils.create_collaboration(
            flask_app_client, user_manager_user, data
        )
        collabs = Collaboration.query.all()
        collab = collabs[0]
        assert len(collabs) == 1

        assert resp.json['edit_state'] == 'not_initiated'
        assert resp.json['read_state'] == 'approved'
        members = resp.json.get('members', [])
        assert len(members) == 2
        assert str(researcher_1.guid) in members
        assert str(researcher_2.guid) in members
    finally:
        if collab:
            collab.delete()
