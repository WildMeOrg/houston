# -*- coding: utf-8 -*-
"""
Application Codex Job_control related tasks for Invoke.
"""

import pprint

from tasks.utils import app_context_task


def _get_jobs(model, stage, guid=None):
    if guid:
        items = model.query.filter(model.guid == guid)
        if items.count() == 0:
            print(f'{str(model)} {guid} not found')
            return
    else:
        items = model.query.filter(model.stage == stage)
    return items


@app_context_task()
def print_all_ags_jobs(context, ags_guid=None, verbose=True):
    """Print out the job status for all the detection jobs for the ags"""
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    for ags in _get_jobs(AssetGroupSighting, AssetGroupSightingStage.detection, ags_guid):
        pprint.pprint(ags.get_jobs_debug(verbose))


@app_context_task()
def print_all_sighting_jobs(context, sighting_guid=None, verbose=True, debug=False):
    """Print out the job status for all the identification jobs for the sighting"""
    from app.modules.sightings.models import Sighting, SightingStage

    if debug:
        breakpoint()

    for sighting in _get_jobs(Sighting, SightingStage.identification, sighting_guid):
        pprint.pprint(sighting.get_job_debug(None, verbose))


@app_context_task()
def print_unreviewed_sighting_jobs(
    context, sighting_guid=None, verbose=True, debug=False
):
    from app.modules.sightings.models import Sighting, SightingStage

    for sighting in _get_jobs(Sighting, SightingStage.un_reviewed, sighting_guid):
        pprint.pprint(sighting.get_job_debug(None, verbose))


@app_context_task()
def print_processed_sighting_jobs(context, sighting_guid=None, verbose=True, debug=False):
    from app.modules.sightings.models import Sighting, SightingStage

    for sighting in _get_jobs(Sighting, SightingStage.processed, sighting_guid):
        pprint.pprint(sighting.get_job_debug(None, verbose))
