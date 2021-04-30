# -*- coding: utf-8 -*-
from pathlib import Path
import tempfile

import pytest

from app.extensions.git_remote import GitRemote


def test_git_remote_local(request):
    td = tempfile.TemporaryDirectory()

    def clean_up_td():
        if Path(td.name).exists():
            td.cleanup()

    request.addfinalizer(clean_up_td)

    projects_json = Path(td.name) / 'projects.json'
    with projects_json.open('w') as f:
        f.write('not json')

    g = GitRemote(td.name)
    assert g.projects.list('TEST') == []

    with projects_json.open('w') as f:
        f.write(
            """\
{"00000000-0000-0000-0000-000000000002": [
    "00000000-0000-0000-0000-000000000002",
    "This is a required PyTest submission (do not delete)",
    {"id": "TEST", "name": "TEST"},
    ["type:pytest-required", "type:test"],
    "/code/_db/git_remote/00000000-0000-0000-0000-000000000002",
    "2021-04-18T21:17:22.880161Z",
    "00000000-0000-0000-0000-000000000002",
    "00000000-0000-0000-0000-000000000002 TEST"
]}"""
        )

    g = GitRemote(td.name)
    assert g.projects.list('00000000-0000-0000-0000-000000000002') == []

    (Path(td.name) / '00000000-0000-0000-0000-000000000002').mkdir()
    g = GitRemote(td.name)
    projects = g.projects.list('00000000-0000-0000-0000-000000000002')
    assert len(projects) == 1
    assert projects[0].id == '00000000-0000-0000-0000-000000000002'

    group_projects = g.groups.get('group_id').projects.list(
        '00000000-0000-0000-0000-000000000002'
    )
    assert group_projects == projects

    projects_json.unlink()

    g = GitRemote(td.name)
    g.auth()  # does not do anything

    user_namespace = g.namespaces.get(id=g.user.id)
    assert user_namespace.id == g.user.id
    namespaces = g.namespaces.list(search='TEST')
    assert len(namespaces) == 1
    assert namespaces[0].id == 'TEST'

    group = g.groups.get('TEST', retry_transient_errors=True)
    assert group.id == 'TEST'
    group = g.groups.create({'name': 'TEST2', 'path': 'test'})
    assert group.id == 'TEST2'

    project = g.projects.create(
        {
            'path': 'project_name',
            'description': 'project description',
            'emails_disabled': True,
            'namespace_id': 'TEST',
            'visibility': 'private',
            'merge_method': 'rebase_merge',
            'tag_list': ['tag:pytest'],
            'lfs_enabled': True,
        },
        retry_transient_errors=True,
    )
    assert project.path == 'project_name'
    assert project.description == 'project description'
    assert project.namespace == {'id': 'TEST', 'name': 'TEST'}
    assert project.tag_list == ['tag:pytest']

    g.projects.create(
        {
            'path': 'different_project',
            'description': 'project description',
            'emails_disabled': True,
            'namespace_id': 'TEST',
            'visibility': 'private',
            'merge_method': 'rebase_merge',
            'tag_list': ['tag:pytest'],
            'lfs_enabled': True,
        },
        retry_transient_errors=True,
    )

    projects = g.projects.list('project_name')
    assert len(projects) == 1
    assert projects[0] == project

    projects = g.projects.list()
    assert len(projects) == 2

    g.projects.delete(project.id)
    assert g.projects.list('project_name') == []

    with pytest.raises(g.GitRemoteDeleteError):
        g.projects.delete(project.id)
