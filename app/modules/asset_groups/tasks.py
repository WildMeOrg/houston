# -*- coding: utf-8 -*-
import logging

import git
from flask import current_app
import requests.exceptions

from app.extensions.celery import celery
from app.extensions.gitlab import GitlabInitializationError

log = logging.getLogger(__name__)


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def ensure_remote(asset_group_guid, additional_tags=[]):
    from .models import AssetGroup

    asset_group = AssetGroup.query.get(asset_group_guid)
    if asset_group is None:
        return  # asset group doesn't exist in the database
    project = current_app.git_backend.get_project(asset_group_guid)
    if not project:
        project = current_app.git_backend.ensure_project(
            asset_group_guid,
            asset_group.get_absolute_path(),
            asset_group.major_type.name,
            asset_group.description,
            additional_tags,
        )

    repo = asset_group.ensure_repository()
    if 'origin' not in repo.remotes:
        repo.create_remote('origin', project.web_url)


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def delete_remote(asset_group_guid, ignore_error=True):
    try:
        current_app.git_backend.delete_remote_project_by_name(asset_group_guid)
    except (GitlabInitializationError, requests.exceptions.RequestException):
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
def git_push(asset_group_guid):
    from .models import AssetGroup, GitLabPAT

    asset_group = AssetGroup.query.get(asset_group_guid)
    if asset_group is None:
        return  # asset group doesn't exist in the database
    repo = asset_group.get_repository()
    if 'origin' not in repo.remotes:
        ensure_remote(asset_group_guid)
    with GitLabPAT(repo):
        log.info('Pushing to authorized URL')
        repo.git.push('--set-upstream', repo.remotes.origin, repo.head.ref)
        log.info(f'...pushed to {repo.head.ref}')


@celery.task(
    autoretry_for=(requests.exceptions.RequestException,),
    default_retry_delay=600,
    max_retries=10,
)
def sage_detection(asset_group_sighting_guid, model):
    from .models import AssetGroupSighting

    asset_group_sighting = AssetGroupSighting.query.find(asset_group_sighting_guid)
    if asset_group_sighting:
        log.debug('Celery running sage detection')
        asset_group_sighting.run_sage_detection(model)
