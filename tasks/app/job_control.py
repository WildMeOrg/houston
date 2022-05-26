# -*- coding: utf-8 -*-
"""
Application Job_control related tasks for Invoke.
"""

import pprint

from app.utils import HoustonException
from tasks.utils import app_context_task


@app_context_task()
def print_jobs(context, verbose=True):
    """Print out all of the outstanding job status"""
    from app.modules.job_control.models import JobControl

    pprint.pprint(JobControl.get_jobs(verbose))


@app_context_task()
def print_last_asset_job(context, asset_guid, verbose=True):
    """Print out the job status for the last detection job for the asset"""
    from app.modules.assets.models import Asset

    try:
        jobs = Asset.get_jobs_for_asset(asset_guid, verbose)
    except HoustonException as ex:
        print(ex.message)

    jobs.sort(key=lambda jb: jb['start'])

    pprint.pprint(jobs[-1])


@app_context_task()
def print_all_asset_jobs(context, asset_guid, verbose=True):
    """Print out the job status for all the detection jobs for the asset"""
    from app.modules.assets.models import Asset

    try:
        jobs = Asset.get_jobs_for_asset(asset_guid, verbose)
    except HoustonException as ex:
        print(ex.message)
        return []

    pprint.pprint(jobs)


@app_context_task()
def print_last_annotation_job(context, annotation_guid, verbose=True):
    """Print out the job status for the last identification job for the annotation"""
    from app.modules.annotations.models import Annotation

    try:
        jobs = Annotation.get_jobs_for_annotation(annotation_guid, verbose)
    except HoustonException as ex:
        print(ex.message)
        return []

    jobs.sort(key=lambda jb: jb['start'])
    pprint.pprint(jobs[-1])


@app_context_task()
def print_all_annotation_jobs(context, annotation_guid, verbose=True):
    """Print out the job status for all the identification jobs for the annotation"""
    from app.modules.annotations.models import Annotation

    try:
        jobs = Annotation.get_jobs_for_annotation(annotation_guid, verbose)
    except HoustonException as ex:
        print(ex.message)
        return []

    pprint.pprint(jobs)


@app_context_task()
def print_scheduled_celery_tasks(context, type=None, verbose=True):
    """Print out the status for all the scheduled celery tasks"""
    from app.utils import get_celery_tasks_scheduled

    scheduled_tasks = get_celery_tasks_scheduled(type)
    pprint.pprint(scheduled_tasks)
