# -*- coding: utf-8 -*-
import tempfile
from unittest import mock
import uuid

import gitlab.exceptions
import pytest

from tests.utils import extension_unavailable


@pytest.mark.skipif(extension_unavailable('gitlab'), reason='GitLab extension disabled')
def test_ensure_project_name_taken(flask_app):
    from app.extensions.gitlab import GitlabInitializationError

    try:
        flask_app.git_backend._ensure_initialized()
    except GitlabInitializationError:
        pytest.skip('Gitlab unavailable')
    projects_create = flask_app.git_backend.gl.projects.create

    def raise_gitlab_exception(*args, error_message='Unknown', **kwargs):
        raise gitlab.exceptions.GitlabCreateError(
            response_code=400,
            error_message=error_message,
        )

    def create_project_raise_gitlab_exception(*args, **kwargs):
        # Create the project
        projects_create(*args, **kwargs)
        # But raise an error
        raise_gitlab_exception(
            error_message="{'name': ['has already been taken'], 'path': ['has already been taken'], 'limit_reached': []}"
        )

    with tempfile.TemporaryDirectory() as repo_path:
        project_name = str(uuid.uuid4())

        # Create the project but gitlab returns an error
        with mock.patch.object(
            flask_app.git_backend.gl.projects,
            'create',
            side_effect=create_project_raise_gitlab_exception,
        ):
            project = flask_app.git_backend.ensure_project(
                project_name, repo_path, 'test', 'project description'
            )
            assert project.name == project_name
            assert project.description == 'project description'

    with tempfile.TemporaryDirectory() as repo_path:
        project_name = str(uuid.uuid4())

        # Project fails to create and gitlab returns an error
        with mock.patch.object(
            flask_app.git_backend.gl.projects,
            'create',
            side_effect=raise_gitlab_exception,
        ):
            with pytest.raises(gitlab.exceptions.GitlabCreateError):
                flask_app.git_backend.ensure_project(
                    project_name, repo_path, 'test', 'project description'
                )
