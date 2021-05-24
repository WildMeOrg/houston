# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils
import uuid


def test_job_control_add_remove(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from app.modules.job_control.models import JobControl
    from app.modules.asset_groups.models import AssetGroupSighting

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = asset_group_utils.TestCreationData(transaction_id)
        data.add_filename(0, 0, test_filename)
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']

        assert 'sightings' in resp.json
        sighting_guid_str = resp.json['sightings'][0]['guid']
        sighting_guid = uuid.UUID(sighting_guid_str)
        asset_group_sighting = AssetGroupSighting.query.get(sighting_guid)

        job_uuid = uuid.uuid4()
        asset_group_sighting.jobs = [
            str(job_uuid),
        ]
        with db.session.begin():
            db.session.refresh(asset_group_sighting)
        JobControl.add_asset_group_sighting_job(job_uuid, sighting_guid)

        JobControl.periodic()

        JobControl.delete_job(job_uuid)

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)
