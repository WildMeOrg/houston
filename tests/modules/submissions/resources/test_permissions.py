# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.submissions.resources.utils as utils
import json
import uuid

from flask import current_app


def test_user_read_permissions(
    flask_app_client,
    admin_user,
    researcher_1,
    readonly_user,
    db,
    test_clone_submission_data,
):
    # Clone as the researcher user and then try to reread as both researcher and readonly user,
    # read by researcher user should succeed, read by readonly user should be blocked

    clone = utils.clone_submission(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        with flask_app_client.login(
            researcher_1,
            auth_scopes=(
                'submissions:read',
                'assets:read',
            ),
        ):
            submission_response = flask_app_client.get(
                '/api/v1/submissions/%s' % test_clone_submission_data['submission_uuid']
            )
            asset_response = flask_app_client.get(
                '/api/v1/assets/%s' % test_clone_submission_data['asset_uuids'][0]
            )
            assert submission_response.status_code == 200
            assert asset_response.status_code == 200

        with flask_app_client.login(
            readonly_user,
            auth_scopes=(
                'submissions:read',
                'assets_read',
            ),
        ):
            submission_response = flask_app_client.get(
                '/api/v1/submissions/%s' % test_clone_submission_data['submission_uuid']
            )
            asset_response = flask_app_client.get(
                '/api/v1/assets/%s' % test_clone_submission_data['asset_uuids'][0]
            )
            assert submission_response.status_code == 403
            assert asset_response.status_code == 401

        # and as no user, removed for now as the
        # @api.login_required(oauth_scopes=['submissions:read']) has been added back to
        # class SubmissionByID and the anonymous user is blocked by that
        # submission_response = flask_app_client.get(
        #        '/api/v1/submissions/%s' % test_clone_submission_uuid
        #    )
        # assert submission_response.status_code == 403

    finally:
        clone.cleanup()


def test_create_patch_submission(flask_app_client, researcher_1, readonly_user, db):
    # pylint: disable=invalid-name
    submission_guid = None

    try:
        from app.modules.submissions.models import Submission, SubmissionMajorType

        test_major_type = SubmissionMajorType.test

        with flask_app_client.login(researcher_1, auth_scopes=('submissions:write',)):
            create_response = flask_app_client.post(
                '/api/v1/submissions/',
                content_type='application/json',
                data=json.dumps(
                    {
                        'major_type': test_major_type,
                        'description': 'This is a test submission, please ignore',
                    }
                ),
            )

        assert create_response.status_code == 200
        submission_guid = create_response.json['guid']
        temp_submission = Submission.query.get(submission_guid)

        with flask_app_client.login(readonly_user, auth_scopes=('submissions:write',)):
            # try to change very polite description slightly and type
            service_major_type = SubmissionMajorType.test

            readonly_patch_response = flask_app_client.patch(
                '/api/v1/submissions/%s' % submission_guid,
                data=json.dumps(
                    {
                        'major_type': service_major_type,
                        'description': 'This is a test submission, kindly ignore',
                    }
                ),
            )
        assert readonly_patch_response.status_code == 403

        with flask_app_client.login(researcher_1, auth_scopes=('submissions:write',)):
            # try to change very polite description slightly and type
            service_major_type = SubmissionMajorType.test

            regular_patch_response = flask_app_client.patch(
                '/api/v1/submissions/%s' % submission_guid,
                data=json.dumps(
                    {
                        'major_type': service_major_type,
                        'description': 'This is a test submission, kindly ignore',
                    }
                ),
            )

        assert regular_patch_response.status_code == 200
        assert regular_patch_response.content_type == 'application/json'
        assert isinstance(regular_patch_response.json, dict)
        assert set(regular_patch_response.json.keys()) >= {'guid', 'major_type'}
        assert regular_patch_response.json['guid'] == submission_guid
        assert regular_patch_response.json['major_type'] == service_major_type

        db.session.refresh(temp_submission)
        assert temp_submission.major_type == service_major_type

        with flask_app_client.login(readonly_user, auth_scopes=('submissions:write',)):
            readonly_delete_response = flask_app_client.delete(
                '/api/v1/submissions/%s' % submission_guid
            )
        assert readonly_delete_response.status_code == 403

        with flask_app_client.login(researcher_1, auth_scopes=('submissions:write',)):
            regular_delete_response = flask_app_client.delete(
                '/api/v1/submissions/%s' % submission_guid
            )
        assert regular_delete_response.status_code == 204

        # And if the submission is already gone, a re attempt at deletion should get the same response
        with flask_app_client.login(researcher_1, auth_scopes=('submissions:write',)):
            regular_delete_response = flask_app_client.delete(
                '/api/v1/submissions/%s' % submission_guid
            )
        assert regular_delete_response.status_code == 204

        # As should a delete of a random uuid
        with flask_app_client.login(researcher_1, auth_scopes=('submissions:write',)):
            regular_delete_response = flask_app_client.delete(
                '/api/v1/submissions/%s' % uuid.uuid4()
            )
        assert regular_delete_response.status_code == 204
    finally:
        current_app.agm.delete_remote_asset_group(temp_submission)
        # Restore original state
        temp_submission = Submission.query.get(submission_guid)
        if temp_submission is not None:
            temp_submission.delete()
