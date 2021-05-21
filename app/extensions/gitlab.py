# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Gitlab Management.

"""
import logging

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
import gitlab
import os

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

    def get_project(self, name):
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

    def _ensure_project(
        self, project_name, repo_path, project_type, description, additional_tags=[]
    ):
        self._ensure_initialized()

        project = self.get_project(project_name)

        if project:
            log.info(
                f'Found existing remote project in GitLab: {project.path_with_namespace}'
            )
        else:
            tag_list = [
                'type:%s' % (project_type,),
            ]
            for tag in additional_tags:
                if isinstance(tag, str):
                    tag_list.append(tag)

            log.info(
                'Creating remote project in GitLab: '
                f'{self.namespace.name}/{project_name} (tags: {tag_list})'
            )
            project = self.gl.projects.create(
                {
                    'path': project_name,
                    'description': description,
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

    def create_project(
        self, project_name, repo_path, project_type, description, additional_tags=[]
    ):
        git_path = os.path.join(repo_path, '.git')
        project = None

        if not os.path.exists(git_path):
            project = self._ensure_project(
                project_name, repo_path, project_type, description, additional_tags
            )

        return project

    def is_project_on_remote(self, project_name):
        project = self.get_project(project_name)
        return project is not None

    def delete_remote_project_by_name(self, project_name):
        self._ensure_initialized()
        project = self.get_project(project_name)
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
