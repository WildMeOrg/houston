# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import filecmp
from os.path import join, basename

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils


def test_create_open_submission(flask_app_client, regular_user, test_root, db):
    # pylint: disable=invalid-name
    temp_submission = None
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)

    try:
        from app.modules.asset_groups.models import AssetGroup

        data = asset_group_utils.TestCreationData(transaction_id)
        data.add_filename(0, 0, test_filename)
        response = asset_group_utils.create_asset_group(
            flask_app_client, regular_user, data.get()
        )

        temp_submission = AssetGroup.query.get(response.json['guid'])

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {
            'guid',
            'commit',
            'major_type',
            'owner_guid',
        }
        # TODO this is what the test checked, that there was not commit, what we are now specifically not permitting
        # assert temp_submission.commit is None
    finally:
        temp_submission.delete_remote()
        # Restore original state
        if temp_submission is not None:
            temp_submission.delete()


def test_submission_streamlined(flask_app_client, test_root, regular_user, db):
    # pylint: disable=invalid-name
    temp_submission = None

    try:
        from app.modules.asset_groups.models import AssetGroup, AssetGroupMajorType

        test_major_type = AssetGroupMajorType.test

        test_image_list = ['zebra.jpg', 'fluke.jpg']
        files = [
            _upload_content(join(test_root, filename)) for filename in test_image_list
        ]

        with flask_app_client.login(regular_user, auth_scopes=('asset_groups:write',)):
            response = flask_app_client.post(
                '/api/v1/asset_groups/streamlined',
                data=dict(
                    major_type=test_major_type,
                    description='Test AssetGroup (streamlined)',
                    files=files,
                ),
            )
        # since we passed file descriptors to files we need to close them now
        [f[0].close() for f in files]

        temp_submission = AssetGroup.query.get(response.json['guid'])

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {
            'guid',
            'commit',
            'major_type',
            'owner_guid',
        }

        repo = temp_submission.get_repository()

        # compares file in local repo
        for filename in test_image_list:
            local_filepath = join(test_root, filename)
            repo_filepath = join(repo.working_tree_dir, '_asset_group', filename)
            assert filecmp.cmp(local_filepath, repo_filepath)

        assert temp_submission.commit == repo.head.object.hexsha
        assert temp_submission.major_type == test_major_type
    finally:
        temp_submission.delete_remote()

        # Restore original state
        if temp_submission is not None:
            temp_submission.delete()


def _upload_content(path):
    bname = basename(path)
    return open(path, 'rb'), bname
