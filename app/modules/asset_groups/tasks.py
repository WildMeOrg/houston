# -*- coding: utf-8 -*-
import logging

from flask import current_app

from app.extensions.celery import celery

log = logging.getLogger(__name__)


@celery.task()
def ensure_remote(asset_group_guid, additional_tags=[]):
    from .models import AssetGroup

    asset_group = AssetGroup.query.get(asset_group_guid)
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


@celery.task()
def delete_remote(asset_group_guid):
    current_app.git_backend.delete_remote_project_by_name(asset_group_guid)


@celery.task()
def git_push(asset_group_guid):
    from .models import AssetGroup, GitLabPAT

    asset_group = AssetGroup.query.get(asset_group_guid)
    repo = asset_group.get_repository()
    if 'origin' not in repo.remotes:
        ensure_remote(asset_group_guid)
    with GitLabPAT(repo):
        log.info('Pushing to authorized URL')
        repo.git.push('--set-upstream', repo.remotes.origin, repo.head.ref)
        log.info(f'...pushed to {repo.head.ref}')
