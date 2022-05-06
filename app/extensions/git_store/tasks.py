# -*- coding: utf-8 -*-
import logging

import git
from flask import current_app
import requests.exceptions
import sqlalchemy.exc

from app.extensions.celery import celery
from app.extensions.gitlab import GitlabInitializationError

log = logging.getLogger(__name__)


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def ensure_remote(git_store_guid, additional_tags=[]):
    from app.extensions.git_store import GitStore

    git_store = GitStore.query.get(git_store_guid)
    if git_store is None:
        return  # git store doesn't exist in the database

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


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def delete_remote(git_store_guid, ignore_error=True):
    try:
        current_app.git_backend.delete_remote_project_by_name(git_store_guid)
    except (GitlabInitializationError, requests.exceptions.RequestException):
        if not ignore_error:
            raise


# RequestException is a base class for all sorts of errors, inc timeouts so this handles them all
@celery.task(
    autoretry_for=(requests.exceptions.RequestException, sqlalchemy.exc.SQLAlchemyError),
    default_retry_delay=10,
    max_retries=10,
)
def git_commit(git_store_guid, description, input_files):
    from app.extensions.git_store import GitStore
    from app.extensions import elasticsearch as es

    git_store = GitStore.query.get(git_store_guid)
    if git_store is None:
        return  # git store doesn't exist in the database

    try:
        git_store.git_commit(
            description,
            input_filenames=input_files,
            update=True,
            commit=True,
        )
    except Exception:
        if git_store.progress_preparation:
            git_store.progress_preparation.fail()
        raise

    assert git_store.progress_preparation.complete
    git_store.post_preparation()

    with es.session.begin(blocking=True, forced=True):
        git_store.index()
        for asset in git_store.assets:
            asset.index()


@celery.task(
    autoretry_for=(
        GitlabInitializationError,
        requests.exceptions.RequestException,
        git.exc.GitCommandError,
    ),
    default_retry_delay=600,
    max_retries=10,
)
def git_push(git_store_guid):
    from app.extensions.git_store import GitStore

    git_store = GitStore.query.get(git_store_guid)
    if git_store is None:
        return  # git store doesn't exist in the database

    repo = git_store.get_repository()
    if 'origin' not in repo.remotes:
        ensure_remote(git_store_guid)
    log.debug('Pushing to authorized URL')
    repo.git.push('--set-upstream', repo.remotes.origin, repo.head.ref)
    log.debug(f'...pushed to {repo.head.ref}')
