# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests.utils import clone_submission
import json

from flask import current_app


def test_user_read_permissions(
    flask_app_client, regular_user, readonly_user, db, test_clone_submission_data
):
    # Clone as the regular user and then try to reread as both regular and readonly user,
    # read by regular user should succeed, read by readonly user should be blocked

    clone = clone_submission(
        flask_app_client,
        regular_user,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        with flask_app_client.login(
            regular_user,
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

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()


def test_create_patch_submission(flask_app_client, regular_user, readonly_user, db):
    # pylint: disable=invalid-name
    submission_guid = None

    try:
        from app.modules.submissions.models import Submission, SubmissionMajorType

        test_major_type = SubmissionMajorType.test

        with flask_app_client.login(regular_user, auth_scopes=('submissions:write',)):
            create_response = flask_app_client.post(
                '/api/v1/submissions/',
                data=json.dumps(
                    {
                        'major_type': test_major_type,
                        'description': 'This is a test submission, please ignore',
                    }
                ),
            )

        # @todo patch via regular user also fails but for a different reason, not permission
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

        with flask_app_client.login(readonly_user, auth_scopes=('submissions:write',)):
            readonly_delete_response = flask_app_client.delete(
                '/api/v1/submissions/%s' % submission_guid
            )
        assert readonly_delete_response.status_code == 403
        with flask_app_client.login(regular_user, auth_scopes=('submissions:write',)):
            regular_delete_response = flask_app_client.delete(
                '/api/v1/submissions/%s' % submission_guid
            )
        # @todo, this shouldn't give an internal error but it's not clear why it is
        assert regular_delete_response.status_code == 500
    except Exception as ex:
        raise ex
    finally:
        current_app.sub.delete_remote_submission(temp_submission)
        # Restore original state
        temp_submission = Submission.query.get(submission_guid)
        if temp_submission is not None:
            temp_submission.delete()
