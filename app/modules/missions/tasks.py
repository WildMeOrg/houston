# -*- coding: utf-8 -*-
import logging

import git
from flask import current_app
import requests.exceptions

from app.extensions.celery import celery
from app.extensions.gitlab import GitlabInitializationError


log = logging.getLogger(__name__)


@celery.task(
    autoretry_for=(requests.exceptions.RequestException,),
    default_retry_delay=600,
    max_retries=10,
)
def send_mws_backend_operation(mission_guid):
    from .models import Mission

    mission = Mission.query.get(mission_guid)

    if mission:
        mission.send_mws_backend_operation()
    else:
        log.warning('Failed to find the mission to perform MWS operation')


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def ensure_remote(mission_collection_guid, additional_tags=[]):
    from .models import MissionCollection

    mission_collection = MissionCollection.query.get(mission_collection_guid)
    if mission_collection is None:
        return  # mission collection doesn't exist in the database
    project = current_app.git_backend.get_project(mission_collection_guid)
    if not project:
        project = current_app.git_backend.ensure_project(
            mission_collection_guid,
            mission_collection.get_absolute_path(),
            mission_collection.major_type.name,
            mission_collection.description,
            additional_tags,
        )

    repo = mission_collection.ensure_repository()
    if 'origin' not in repo.remotes:
        repo.create_remote('origin', project.ssh_url_to_repo)


@celery.task(
    autoretry_for=(GitlabInitializationError, requests.exceptions.RequestException),
    default_retry_delay=600,
    max_retries=10,
)
def delete_remote(mission_collection_guid, ignore_error=True):
    try:
        current_app.git_backend.delete_remote_project_by_name(mission_collection_guid)
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
def git_push(mission_collection_guid):
    from .models import MissionCollection

    mission_collection = MissionCollection.query.get(mission_collection_guid)
    if mission_collection is None:
        return  # mission collection doesn't exist in the database
    repo = mission_collection.get_repository()
    if 'origin' not in repo.remotes:
        ensure_remote(mission_collection_guid)
    log.debug('Pushing to authorized URL')
    repo.git.push('--set-upstream', repo.remotes.origin, repo.head.ref)
    log.debug(f'...pushed to {repo.head.ref}')
