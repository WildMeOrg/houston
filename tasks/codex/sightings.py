# -*- coding: utf-8 -*-
"""
Application AssetGroup management related tasks for Invoke.
"""

import pprint

from tasks.utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing sightings.
    """
    from app.modules.sightings.models import Sighting

    for sighting in Sighting.query.all():
        print(f'Sighting : {sighting}')


@app_context_task
def list_all_sightings_in_stage(context, stage):
    """
    Show all sightings in the stage, options are identification, un_reviewed, processed, failed.
    """
    from app.modules.sightings.models import Sighting

    for sighting in Sighting.query.filter(Sighting.stage == stage).all():
        print(f'Sighting : {sighting}')


@app_context_task
def details(context, guid):
    """
    Show full existing of a specific sighting.

    Command Line:
    > invoke codex.sightings.details 00000000-0000-0000-0000-000000000002
    """

    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(guid)

    if sighting is None:
        print(f'Sighting {guid} not found')
        return

    # Just reuse the debug schema
    from app.modules.sightings.schemas import DebugSightingSchema

    schema = DebugSightingSchema()
    import json

    print(json.dumps(schema.dump(sighting).data, indent=4, sort_keys=True))


@app_context_task()
def print_sighting_id_resullt(context, sighting_guid):
    """Print out the job status for all the identification jobs for the sighting"""
    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(sighting_guid)
    if not sighting:
        print(f'Sighting {sighting_guid} not found')
    pprint.pprint(sighting.get_id_result())


@app_context_task
def send_one_to_detection(context, model, guid):
    """
    Send Assets from this Sighting to detection (--model MODEL, like seals_v1)

    """

    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(guid)

    if sighting is None:
        print(f'Sighting {guid} not found')
        return
    _send_sighting_to_detection(sighting, model)


def _send_sighting_to_detection(sighting, model):
    from app.extensions import db
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    if sighting.asset_group_sighting:
        ags = sighting.asset_group_sighting
        ags.config['detections'] = [model]
        ags.config['sighting']['speciesDetectionModel'] = [model]
        ags.config = ags.config
        ags.stage = AssetGroupSightingStage.detection
        db.session.merge(ags)
        db.session.refresh(ags)
        ags.start_detection(True)

    else:
        if not sighting.get_assets():
            print('No assets to find AssetGroup')
        ag = sighting.get_assets()[0].git_store
        ag.init_progress_detection()
        sconf = {'assetReferences': []}
        for asset in sighting.get_assets():
            sconf['assetReferences'].append(asset.filename)
        # note: this AGS does *not* get persisted to db, but thats how we started?
        ags = AssetGroupSighting(
            asset_group=ag,
            sighting_config=sconf,
            detection_configs=[model],
        )
        ags.stage = AssetGroupSightingStage.detection
        db.session.merge(ags)
        db.session.refresh(ags)
        ags.start_detection(True)


@app_context_task
def send_batch_to_detection(context, model, batchsize=10):
    """
    Send Assets from N Sightings to detection (--model MODEL, like seals_v1)

    """

    from app.extensions import db
    from app.modules.sightings.models import Sighting

    sighting_guids = []
    res = db.session.execute(
        f'SELECT DISTINCT(sighting.guid) FROM sighting JOIN sighting_assets ON (sighting.guid=sighting_guid) JOIN asset ON (sighting_assets.asset_guid=asset.guid) JOIN git_store ON (git_store_guid=git_store.guid) WHERE progress_detection_guid IS NULL ORDER BY sighting.guid LIMIT {batchsize}'
    )
    for row in res:
        sighting_guids.append(row[0])

    ct = 1
    for guid in sighting_guids:
        sighting = Sighting.query.get(guid)
        assert sighting
        print(f'[{ct} of {batchsize}] processing {guid}')
        ct += 1
        _send_sighting_to_detection(sighting, model)
