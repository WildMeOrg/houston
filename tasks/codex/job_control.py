# -*- coding: utf-8 -*-
"""
Application Codex Job_control related tasks for Invoke.
"""

from tasks.utils import app_context_task
import pprint


@app_context_task()
def print_all_ags_jobs(context, ags_guid, verbose=True):
    """Print out the job status for all the detection jobs for the ags"""
    from app.modules.asset_groups.models import AssetGroupSighting

    ags = AssetGroupSighting.query.get(ags_guid)
    if not ags:
        print(f'AssetGroupSighting {ags_guid} not found')
        return
    pprint.pprint(ags.get_jobs_debug(verbose))


@app_context_task()
def print_all_sighting_jobs(context, sighting_guid, verbose=True):
    """Print out the job status for all the identification jobs for the sighting"""
    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(sighting_guid)
    if not sighting:
        print(f'Sighting {sighting_guid} not found')
    pprint.pprint(sighting.get_job_debug(None, verbose))
