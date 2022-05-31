# -*- coding: utf-8 -*-
import logging

import git
import requests.exceptions
import sqlalchemy.exc
from flask import current_app

from app.extensions.celery import celery
from app.extensions.gitlab import GitlabInitializationError

log = logging.getLogger(__name__)


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def ensure_remote(git_store_guid, additional_tags=[], ignore_error=True):
    from app.extensions.git_store import GitStore

    git_store = GitStore.query.get(git_store_guid)
    if git_store is None:
        return False  # git store doesn't exist in the database

    try:
        project = current_app.git_backend.get_project(git_store_guid)
        if not project:
            project = current_app.git_backend.ensure_project(
                git_store_guid,
                git_store.get_absolute_path(),
                git_store.major_type.name,
                git_store.description,
                additional_tags,
            )

        repo = git_store.ensure_repository()
        if 'origin' not in repo.remotes:
            repo.create_remote('origin', project.ssh_url_to_repo)

        return True
    except GitlabInitializationError:
        log.warning('GitLab Initialization Error in tasks.ensure_remote()')
        if not ignore_error:
            raise

    return False


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def delete_remote(git_store_guid, ignore_error=True):
    try:
        current_app.git_backend.delete_remote_project_by_name(git_store_guid)
    except (GitlabInitializationError, requests.exceptions.RequestException):
        log.warning('GitLab Initialization Error in tasks.delete_remote()')
        if not ignore_error:
            raise


# RequestException is a base class for all sorts of errors, inc timeouts so this handles them all
@celery.task(
    autoretry_for=(requests.exceptions.RequestException, sqlalchemy.exc.SQLAlchemyError),
    default_retry_delay=10,
    max_retries=10,
)
def git_commit(git_store_guid, description, input_files, ignore_error=True):
    from app.extensions.git_store import GitStore

    git_store = GitStore.query.get(git_store_guid)
    if git_store is None:
        return  # git store doesn't exist in the database

    try:
        git_store.git_commit_worker(description, input_files)
    except GitlabInitializationError:
        log.warning('GitLab Initialization Error in tasks.git_commit()')
        if not ignore_error:
            raise


@celery.task(
    autoretry_for=(
        GitlabInitializationError,
        requests.exceptions.RequestException,
        git.exc.GitCommandError,
    ),
    default_retry_delay=600,
    max_retries=10,
)
def git_push(git_store_guid, ignore_error=True):
    from app.extensions.git_store import GitStore

    git_store = GitStore.query.get(git_store_guid)
    if git_store is None:
        return  # git store doesn't exist in the database

    try:
        repo = git_store.get_repository()

        exists = repo and 'origin' in repo.remotes
        if not exists:
            exists = ensure_remote(git_store_guid)

        if exists:
            log.debug('Pushing to authorized URL')
            if len(repo.remotes) > 0:
                repo.git.push('--set-upstream', repo.remotes.origin, repo.head.ref)
                log.debug(f'...pushed to {repo.head.ref}')
    except GitlabInitializationError:
        log.warning('GitLab Initialization Error in tasks.git_push()')
        if not ignore_error:
            raise
