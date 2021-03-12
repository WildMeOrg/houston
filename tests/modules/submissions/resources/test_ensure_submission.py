# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid
import tests.modules.submissions.resources.utils as utils


def test_ensure_submission_by_uuid(
    flask_app_client, admin_user, researcher_1, db, test_submission_uuid
):
    utils.clone_submission(
        flask_app_client, admin_user, researcher_1, test_submission_uuid
    )


def test_ensure_empty_submission_by_uuid(
    flask_app_client, admin_user, researcher_1, db, test_empty_submission_uuid
):
    utils.clone_submission(
        flask_app_client, admin_user, researcher_1, test_empty_submission_uuid
    )


def test_ensure_clone_submission_by_uuid(
    flask_app_client, admin_user, researcher_1, db, test_clone_submission_data
):
    from app.modules.submissions.models import SubmissionMajorType
    from app.modules.assets.models import Asset

    clone = utils.clone_submission(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        assert clone.submission.major_type == SubmissionMajorType.test
        # assert clone.submission.commit == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        assert clone.submission.commit_mime_whitelist_guid == uuid.UUID(
            '4d46c55d-accf-29f1-abe7-a24839ec1b95'
        )

        # assert clone.submission.commit_houston_api_version == '0.1.0.xxxxxxxx'
        assert (
            clone.submission.description
            == 'This is a required PyTest submission (do not delete)'
        )

        # Checks that there are two valid Assets in the database
        assert len(clone.submission.assets) == 3
        temp_assets = sorted(clone.submission.assets)
        expected_guid_list = [
            uuid.UUID(test_clone_submission_data['asset_uuids'][0]),
            uuid.UUID(test_clone_submission_data['asset_uuids'][1]),
            uuid.UUID(test_clone_submission_data['asset_uuids'][2]),
        ]

        for asset, expected_guid in zip(temp_assets, expected_guid_list):
            db_asset = Asset.query.get(asset.guid)
            assert asset == db_asset
            assert asset.guid == expected_guid

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()
