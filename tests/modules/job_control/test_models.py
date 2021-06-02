# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils
import uuid
import json


def test_job_control_add_remove(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from app.modules.job_control.models import JobControl
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None

    try:
        data = asset_group_utils.TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        data.set_field('speciesDetectionModel', ['ActualModel'])
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']

        assert 'sightings' in resp.json
        sighting_guid_str = resp.json['sightings'][0]['guid']
        sighting_guid = uuid.UUID(sighting_guid_str)
        asset_group_sighting = AssetGroupSighting.query.get(sighting_guid)

        job_control_entries = JobControl.query.all()
        assert len(job_control_entries) == 0
        assert asset_group_sighting.stage == AssetGroupSightingStage.detection
        asset_group_sighting.start_job('ActualModel')
        job_control_entries = JobControl.query.all()
        assert len(job_control_entries) == 1
        assert (
            job_control_entries[0].asset_group_sighting_uuid == asset_group_sighting.guid
        )
        assert job_control_entries[0].annotation_uuid is None
        jobs = json.loads(asset_group_sighting.jobs)

        assert len(jobs.keys()) == 1

        JobControl.periodic()
        for job_id in jobs.keys():
            asset_group_sighting.job_complete(job_id)

        job_control_entries = JobControl.query.all()
        assert len(job_control_entries) == 0
        JobControl.periodic()

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)
