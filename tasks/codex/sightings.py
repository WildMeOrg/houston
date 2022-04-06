# -*- coding: utf-8 -*-
"""
Application AssetGroup management related tasks for Invoke.
"""

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
