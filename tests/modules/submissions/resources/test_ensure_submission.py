# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid
from tests.utils import clone_submission


def test_ensure_submission_by_uuid(
    flask_app_client, regular_user, db, test_submission_uuid
):
    clone_submission(flask_app_client, regular_user, test_submission_uuid)


def test_ensure_empty_submission_by_uuid(
    flask_app_client, regular_user, db, test_empty_submission_uuid
):
    clone_submission(flask_app_client, regular_user, test_empty_submission_uuid)


def test_ensure_clone_submission_by_uuid(
    flask_app_client, regular_user, db, test_clone_submission_uuid
):
    from app.modules.submissions.models import SubmissionMajorType
    from app.modules.assets.models import Asset

    clone = clone_submission(
        flask_app_client, regular_user, test_clone_submission_uuid, later_usage=True
    )

    try:
        assert clone.temp_submission.major_type == SubmissionMajorType.test
        assert clone.temp_submission.commit == 'e94db0cf015c6c84ab1668186924dc985fc472d6'
        assert clone.temp_submission.commit_mime_whitelist_guid == uuid.UUID(
            '4d46c55d-accf-29f1-abe7-a24839ec1b95'
        )

        assert clone.temp_submission.commit_houston_api_version == '0.1.0.8b208226'
        assert clone.temp_submission.description == 'Test Submission (streamlined)'

        # Checks that there are two valid Assets in the database
        assert len(clone.temp_submission.assets) == 2
        temp_assets = sorted(clone.temp_submission.assets)
        expected_guid_list = [
            uuid.UUID('3abc03a8-39c8-42c4-bedb-e08ccc485396'),
            uuid.UUID('aee00c38-137e-4392-a4d9-92b545a9efb0'),
        ]

        for asset, expected_guid in zip(temp_assets, expected_guid_list):
            db_asset = Asset.query.get(asset.guid)
            assert asset == db_asset
            assert asset.guid == expected_guid

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()


def test_ensure_permissions(
    flask_app_client, regular_user, readonly_user, db, test_clone_submission_uuid
):
    # Clone as the regular user and then try to reread as both regular and readonly user,
    # read by regular user should succeed, read by readonly user should be blocked

    clone = clone_submission(
        flask_app_client, regular_user, test_clone_submission_uuid, later_usage=True
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
                '/api/v1/submissions/%s' % test_clone_submission_uuid
            )
            asset_response = flask_app_client.get(
                '/api/v1/assets/3abc03a8-39c8-42c4-bedb-e08ccc485396'
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
                '/api/v1/submissions/%s' % test_clone_submission_uuid
            )
            asset_response = flask_app_client.get(
                '/api/v1/assets/3abc03a8-39c8-42c4-bedb-e08ccc485396'
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
