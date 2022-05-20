# -*- coding: utf-8 -*-
import io
import pathlib
import re
from unittest import mock
import uuid

from invoke import MockContext
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_from_path(flask_app, test_root, admin_user, request):
    from app.modules.asset_groups.models import AssetGroup

    with mock.patch('app.create_app'):
        from tasks.codex.asset_groups import create_asset_group_from_path

        with pytest.raises(Exception) as e:
            create_asset_group_from_path(
                MockContext(), test_root, 'nobody@nowhere.org', 'Expected failure'
            )
            assert str(e) == "User with email 'nobody@nowhere.org' does not exist."

        with pytest.raises(IOError) as e:
            create_asset_group_from_path(
                MockContext(), '/does-not-exist', admin_user.email, 'Expected failure'
            )
            assert str(e) == 'The path /does-not-exist does not exist.'

        with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            from app.extensions.gitlab import GitlabInitializationError

            asset_group_guids = [a.guid for a in AssetGroup.query.all()]
            try:
                create_asset_group_from_path(
                    MockContext(), test_root, admin_user.email, 'AssetGroup creation test'
                )
            except GitlabInitializationError:
                asset_group = AssetGroup.query.filter(
                    AssetGroup.guid.notin_(asset_group_guids)
                ).first()
                asset_group.delete()
                pytest.skip('Gitlab unavailable')
            last_line = stdout.getvalue().splitlines()[-1]
            assert last_line.startswith('Created and pushed new asset_group:')
            guid = re.search(r'<AssetGroup\(guid=([a-f0-9-]*)', last_line).group(1)

    asset_group = AssetGroup.query.get(guid)
    assert asset_group is not None
    request.addfinalizer(asset_group.delete)

    assert asset_group.owner == admin_user
    dir_files = sorted(f.name for f in pathlib.Path(test_root).glob('*'))
    asset_paths = sorted([a.path for a in asset_group.assets])
    assert dir_files == asset_paths
    assert asset_group.description == 'AssetGroup creation test'


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_clone_asset_group_from_gitlab(
    flask_app, db, test_asset_group_uuid, researcher_1
):
    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.asset_groups.models import AssetGroup

    # Patch delete_remote so it doesn't delete the gitlab project
    with mock.patch('app.extensions.git_store.tasks.delete_remote'):
        AssetGroup.query.get(test_asset_group_uuid).delete()

    try:
        flask_app.git_backend._ensure_initialized()
    except GitlabInitializationError:
        pytest.skip('Gitlab unavailable')
    clone_root = pathlib.Path(flask_app.config['ASSET_GROUP_DATABASE_PATH'])
    repo_path = clone_root / str(test_asset_group_uuid)

    with mock.patch('app.create_app'):
        from tasks.codex.asset_groups import clone_asset_group_from_gitlab

        with pytest.raises(Exception) as e:
            clone_asset_group_from_gitlab(
                MockContext(), str(test_asset_group_uuid), 'nobody@nowhere.org'
            )
            assert str(e) == "User with email 'nobody@nowhere.org' does not exist."

        with pytest.raises(ValueError) as e:
            random_uuid = uuid.uuid4()
            clone_asset_group_from_gitlab(
                MockContext(), str(random_uuid), researcher_1.email
            )
            assert (
                str(e)
                == f"Could not find asset_group in GitLab using GUID '{random_uuid}'"
            )

        with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            assert not repo_path.exists()
            clone_asset_group_from_gitlab(
                MockContext(), str(test_asset_group_uuid), researcher_1.email
            )
            assert 'Cloned asset_group from GitLab' in stdout.getvalue()
            assert repo_path.exists()

        with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            # do it again
            clone_asset_group_from_gitlab(
                MockContext(), str(test_asset_group_uuid), researcher_1.email
            )
            assert 'AssetGroup is already cloned locally' in stdout.getvalue()
            assert repo_path.exists()

    with mock.patch('app.extensions.git_store.tasks.delete_remote'):
        AssetGroup.query.get(test_asset_group_uuid).delete()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_list_all(flask_app, test_asset_group_uuid, test_empty_asset_group_uuid):
    with mock.patch('app.create_app'):
        from app.modules.asset_groups.models import AssetGroup
        from tasks.codex.asset_groups import list_all

        with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            list_all(MockContext())
            asset_groups = stdout.getvalue()
            assert f'<AssetGroup(guid={test_asset_group_uuid}, )' in asset_groups
            assert f'<AssetGroup(guid={test_empty_asset_group_uuid}, )' in asset_groups

        with mock.patch('app.extensions.git_store.tasks.delete_remote'):
            AssetGroup.query.get(test_asset_group_uuid).delete()
            AssetGroup.query.get(test_empty_asset_group_uuid).delete()
