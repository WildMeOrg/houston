# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import logging


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def disabled_test_create_bulk_asset_group_and_detection(
    flask_app_client, researcher_1, test_root, request
):
    # pylint: disable=invalid-name
    from app.modules.asset_groups.models import AssetGroup

    asset_group_uuid = None
    try:
        data = asset_group_utils.get_bulk_creation_data(test_root, request).get()
        data['speciesDetectionModel'] = ['african_terrestrial']

        resp = asset_group_utils.create_asset_group(flask_app_client, researcher_1, data)
        asset_group_uuid = resp.json['guid']
        asset_group = AssetGroup.query.get(asset_group_uuid)

        for sighting in asset_group.asset_group_sightings:
            log.info('sighting = %r' % (sighting,))
            log.info('sighting.config = %r' % (sighting.config,))
            log.info('sighting.stage = %r' % (sighting.stage,))
            log.info('sighting.jobs = %r' % (sighting.jobs,))
            assert len(sighting.jobs) > 0
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
