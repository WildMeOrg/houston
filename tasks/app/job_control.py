# -*- coding: utf-8 -*-
"""
Application EDM related tasks for Invoke.
"""

from ._utils import app_context_task


@app_context_task()
def print_jobs(context):
    """Print out all of the outstanding job status"""
    from app.modules.job_control.models import JobControl

    JobControl.print_jobs()


def get_jobs_for_asset(asset_guid, verbose):
    from app.modules.assets.models import Asset
    from app.modules.asset_groups.models import AssetGroup, AssetGroupSighting  # noqa

    asset = Asset.query.get(asset_guid)
    if not asset:
        print(f'Asset {asset_guid} not found')
        return []

    asset_group_sightings = asset.asset_group.get_asset_group_sightings_for_asset(asset)

    jobs = {}
    for ags in asset_group_sightings:
        jobs.update(ags.get_job_details(verbose))

    return jobs


@app_context_task()
def print_last_asset_job(context, asset_guid, verbose=False):
    """Print out the job status for the last detection job for the asset"""

    jobs = get_jobs_for_asset(asset_guid, verbose)

    last_job_id = None
    last_job = {}
    for job_id in jobs.keys():
        if not last_job_id or jobs[job_id]['start'] > last_job['start']:
            last_job_id = job_id
            last_job = jobs[job_id]

    print(
        f"Last Job {last_job_id} Active:{last_job['active']}"
        f"Started (UTC):{last_job['start']} model:{last_job['model']}"
    )
    if verbose:
        print(f"\n\tRequest:{last_job['request']}\n\tResponse:{last_job['response']}")


@app_context_task()
def print_all_asset_jobs(context, asset_guid, verbose=False):
    """Print out the job status for all the detection jobs for the asset"""
    jobs = get_jobs_for_asset(asset_guid, verbose)

    for job_id in jobs.keys():
        job = jobs[job_id]
        print(
            f"Job {job_id} Active:{job['active']} Started (UTC):{job['start']} model:{job['model']}"
        )
        if verbose:
            print(f"\n\tRequest:{job['request']}\n\tResponse:{job['response']}")
