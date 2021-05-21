# -*- coding: utf-8 -*-
from flask import current_app

from app.extensions.celery import celery


@celery.task()
def delete_remote(asset_group_guid):
    current_app.git_backend.delete_remote_project_by_name(asset_group_guid)
