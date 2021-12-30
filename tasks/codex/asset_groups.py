# -*- coding: utf-8 -*-
"""
Application AssetGroup management related tasks for Invoke.
"""

from tasks.utils import app_context_task
import os


@app_context_task(
    help={
        'path': '/path/to/asset_group/folder/ or /path/to/asset_group/file.ext',
        'email': 'temp@localhost.  This is the email for the user who will be assigned as the owner of the new asset_group',
        'description': 'An optional description for the asset_group',
    }
)
def create_asset_group_from_path(
    context,
    path,
    email,
    description=None,
):
    """
    Create a new asset_group via a local file or folder path.

    Command Line:
    > invoke codex.asset_groups.create-asset_group-from-path --path tests/asset_groups/test-000/ --email jason@wildme.org
    """
    from app.modules.users.models import User
    from app.modules.asset_groups.models import AssetGroup, AssetGroupMajorType
    from app.modules.asset_groups.tasks import git_push
    from app.extensions import db
    import socket

    user = User.find(email=email)

    if user is None:
        raise Exception("User with email '%s' does not exist." % email)

    absolute_path = os.path.abspath(os.path.expanduser(path))
    print('Attempting to import path: %r' % (absolute_path,))

    if not os.path.exists(path):
        raise IOError('The path %r does not exist.' % (absolute_path,))

    args = {
        'owner_guid': user.guid,
        'major_type': AssetGroupMajorType.filesystem,
        'description': description,
    }
    asset_group = AssetGroup(**args)

    with db.session.begin():
        db.session.add(asset_group)

    db.session.refresh(asset_group)

    # Make sure that the repo for this asset group exists
    asset_group.ensure_repository()

    asset_group.git_copy_path(absolute_path)

    hostname = socket.gethostname()
    asset_group.git_commit('Initial commit via CLI on host %r' % (hostname,))

    git_push(str(asset_group.guid))

    print('Created and pushed new asset_group: %r' % (asset_group,))


@app_context_task(
    help={
        'guid': 'A UUID4 for the asset_group',
        'email': 'temp@localhost.  This is the email for the user who will be assigned as the owner of the new asset_group',
    }
)
def clone_asset_group_from_gitlab(
    context,
    guid,
    email,
):
    """
    Clone an existing asset_group from the external GitLab asset_group archive

    Command Line:
    > invoke codex.asset_groups.clone-asset_group-from-gitlab --guid 00000000-0000-0000-0000-000000000002 --email jason@wildme.org
    """
    from app.modules.users.models import User
    from app.modules.asset_groups.models import AssetGroup

    user = User.find(email=email)

    if user is None:
        raise Exception("User with email '%s' does not exist." % email)

    asset_group = AssetGroup.query.get(guid)

    if asset_group is not None:
        print('AssetGroup is already cloned locally:\n\t%s' % (asset_group,))
        asset_group.ensure_repository()
        return

    asset_group = AssetGroup.ensure_asset_group(guid, owner=user)

    if asset_group is None:
        raise ValueError('Could not find asset_group in GitLab using GUID %r' % (guid,))

    print('Cloned asset_group from GitLab:')
    print('\tAssetGroup: %r' % (asset_group,))
    print('\tLocal Path: %r' % (asset_group.get_absolute_path(),))


@app_context_task
def list_all(context):
    """
    Show existing asset_groups.
    """
    from app.modules.asset_groups.models import AssetGroup

    asset_groups = AssetGroup.query.all()

    for asset_group in asset_groups:
        print('AssetGroup : {} {}'.format(asset_group, asset_group.assets))


@app_context_task
def details(context, guid):
    """
    Show full existing of a specific asset_group.

    Command Line:
    > invoke codex.asset_groups.details 00000000-0000-0000-0000-000000000002
    """

    from app.modules.asset_groups.models import AssetGroup

    asset_group = AssetGroup.query.get(guid)

    if asset_group is None:
        print(f'AssetGroup {guid} not found')
        return

    # Just reuse the debug schema
    from app.modules.asset_groups.schemas import DebugAssetGroupSchema

    schema = DebugAssetGroupSchema()
    import json

    print(json.dumps(schema.dump(asset_group).data, indent=4, sort_keys=True))
