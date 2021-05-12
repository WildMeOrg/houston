# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Gitlab Management.

"""
import logging

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
import gitlab
import git
import json
import os
from pathlib import Path

import keyword


KEYWORD_SET = set(keyword.kwlist)


GITLAB_TIMESTAMP_FORMAT_STR = '%Y-%m-%dT%H:%M:%S.%fZ'  # Ex: '2020-10-23T16:57:52.066Z'


log = logging.getLogger(__name__)


class GitlabManager(object):
    def __init__(self, pre_initialize=False, *args, **kwargs):
        super(GitlabManager, self).__init__(*args, **kwargs)
        self.initialized = False

        self.gl = None
        self.namespace = None

        if pre_initialize:
            self._ensure_initialized()

    @property
    def _gitlab_group(self):
        """Lookup the GitLab Group from the Namespace"""

        self._ensure_initialized()
        # Lookup the cached group
        if hasattr(self, '_gl_group'):
            return self._gl_group

        # Lookup and cache the Group object
        group_id = self.namespace.id
        self._gl_group = self.gl.groups.get(group_id, retry_transient_errors=True)
        return self._gl_group

    def _get_gitlab_project(self, name):
        """Lookup a specific gitlab project/repo by name that is within the preconfigured namespace/group"""
        self._ensure_initialized()

        # Try to find remote project by asset_group UUID
        projects = self._gitlab_group.projects.list(
            search=name, retry_transient_errors=True
        )
        if len(projects) != 0:
            assert len(projects) >= 1, 'Failed to create gitlab namespace!?'
            return projects[0]
        else:
            return None

    def _ensure_initialized(self):
        if not self.initialized:
            assert self.gl is None

            remote_uri = current_app.config.get('GITLAB_REMOTE_URI', None)
            remote_personal_access_token = current_app.config.get(
                'GITLAB_REMOTE_LOGIN_PAT', None
            )
            remote_namespace = current_app.config.get('GITLAB_NAMESPACE', None)

            log.info('Logging into Asset Group GitLab...')
            log.info('\t URI: %r' % (remote_uri,))
            log.info('\t NS : %r' % (remote_namespace,))
            if current_app.config.get('DEBUG', False):
                log.info(f'\t GITLAB_REMOTE_LOGIN_PAT: {remote_personal_access_token}')

            try:
                self.gl = gitlab.Gitlab(
                    remote_uri, private_token=remote_personal_access_token
                )
                self.gl.auth()
                log.info('Logged in: %r' % (self.gl,))

                # Check for namespace
                if remote_namespace is None:
                    namespace = self.gl.namespaces.get(id=self.gl.user.id)
                else:
                    namespaces = self.gl.namespaces.list(search=remote_namespace)
                    if len(namespaces) == 0:
                        path = remote_namespace.lower()
                        group = self.gl.groups.create(
                            {'name': remote_namespace, 'path': path}
                        )
                        namespace = self.gl.namespaces.get(id=group.id)
                        namespaces = self.gl.namespaces.list(search=remote_namespace)
                    assert len(namespaces) >= 1, 'Failed to create gitlab namespace!?'
                    namespace = namespaces[0]

                self.namespace = namespace
                log.info('Using namespace: %r' % (self.namespace,))

                self.initialized = True
            except Exception:
                self.gl = None
                self.namespace = None
                self.initialized = False

                if current_app.debug:
                    log.exception('problem initializing GitLab integration')

                raise RuntimeError(
                    'GitLab remote failed to authenticate and/or initialize'
                )

    def _ensure_project(self, asset_group, additional_tags=[]):
        group_path = asset_group.get_absolute_path()

        self._ensure_initialized()

        project_name = str(asset_group.guid)
        project = self._get_gitlab_project(project_name)

        if project:
            log.info(
                f'Found existing remote project in GitLab: {project.path_with_namespace}'
            )
            # Clone remote repo
            if os.path.exists(group_path):
                asset_group.git_pull()
            else:
                asset_group.git_clone(project)
        else:
            tag_list = [
                'type:%s' % (asset_group.major_type.name,),
            ]
            for tag in additional_tags:
                if isinstance(tag, str):
                    tag_list.append(tag)

            log.info(
                'Creating remote project in GitLab: '
                f'{self.namespace.name}/{asset_group.guid} (tags: {tag_list})'
            )
            project = self.gl.projects.create(
                {
                    'path': project_name,
                    'description': asset_group.description,
                    'emails_disabled': True,
                    'namespace_id': self.namespace.id,
                    'visibility': 'private',
                    'merge_method': 'rebase_merge',
                    'tag_list': tag_list,
                    'lfs_enabled': True,
                    # 'tag_list': [],
                },
                retry_transient_errors=True,
            )

        return project

    def _ensure_repository_files(self, group_path, project):

        # AssetGroup Repo Structure:
        #     _db/assetGroup/<asset_group GUID>/
        #         - .git/
        #         - _asset_group/
        #         - - <user's uploaded data>
        #         - _assets/
        #         - - <symlinks into _asset_group/ folder> with name <asset GUID >.ext --> ../_asset_group/path/to/asset/original_name.ext
        #         - metadata.json

        if not os.path.exists(group_path):
            # Initialize local repo
            log.info('Creating asset_groups structure: %r' % (group_path,))
            os.mkdir(group_path)

        # Create the repo
        git_path = os.path.join(group_path, '.git')
        if not os.path.exists(git_path):
            repo = git.Repo.init(group_path)
            assert len(repo.remotes) == 0
            gitlab_remote_public_name = current_app.config.get('GITLAB_PUBLIC_NAME', None)
            gitlab_remote_email = current_app.config.get('GITLAB_EMAIL', None)
            assert None not in [gitlab_remote_public_name, gitlab_remote_email]
            repo.git.config('user.name', gitlab_remote_public_name)
            repo.git.config('user.email', gitlab_remote_email)
        else:
            repo = git.Repo(group_path)

        if project is not None:
            if len(repo.remotes) == 0:
                origin = repo.create_remote('origin', project.web_url)
            else:
                origin = repo.remotes.origin
            assert origin.url == project.web_url

        asset_group_path = os.path.join(group_path, '_asset_group')
        if not os.path.exists(asset_group_path):
            os.mkdir(asset_group_path)
        Path(os.path.join(asset_group_path, '.touch')).touch()

        assets_path = os.path.join(group_path, '_assets')
        if not os.path.exists(assets_path):
            os.mkdir(assets_path)
        Path(os.path.join(assets_path, '.touch')).touch()

        metatdata_path = os.path.join(group_path, 'metadata.json')
        if not os.path.exists(metatdata_path):
            with open(metatdata_path, 'w') as metatdata_file:
                json.dump({}, metatdata_file)

        with open(metatdata_path, 'r') as metatdata_file:
            group_metadata = json.load(metatdata_file)

        with open(metatdata_path, 'w') as metatdata_file:
            json.dump(group_metadata, metatdata_file)

        log.info('LOCAL  REPO: %r' % (repo.working_tree_dir,))
        log.info('REMOTE REPO: %r' % (project.web_url,))

        return repo

    def ensure_repository(self, asset_group):
        if self.get_repository(asset_group) is None:
            self.create_repository(asset_group)

    def create_repository(self, asset_group, additional_tags=[]):
        group_path = asset_group.get_absolute_path()
        git_path = os.path.join(group_path, '.git')

        if os.path.exists(git_path):
            repo = git.Repo(group_path)
        else:
            project = self._ensure_project(asset_group, additional_tags)
            repo = self._ensure_repository_files(group_path, project)

        return repo

    def get_repository(self, asset_group):
        if asset_group is None:
            return None
        group_path = asset_group.get_absolute_path()
        git_path = os.path.join(group_path, '.git')

        if os.path.exists(git_path):
            repo = git.Repo(group_path)
        else:
            repo = None

        return repo

    def assert_taglist(self, asset_group_uuid, whitelist_tag):
        project_name = str(asset_group_uuid)
        project = self._get_gitlab_project(project_name)
        assert (
            whitelist_tag in project.tag_list
        ), 'Project %r needs to be re-provisioned: %r' % (
            project,
            project.tag_list,
        )

    def is_asset_group_on_remote(self, asset_group_uuid):
        project = self._get_gitlab_project(asset_group_uuid)
        return project is not None

    def delete_remote_asset_group(self, asset_group):
        self._ensure_initialized()
        project = self._get_gitlab_project(asset_group.guid)
        if project:
            self.delete_remote_project(project)

    def delete_remote_project(self, project):
        self._ensure_initialized()
        try:
            self.gl.projects.delete(project.id)
            return True
        except gitlab.GitlabDeleteError:
            pass
        return False


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.git_backend = GitlabManager()
