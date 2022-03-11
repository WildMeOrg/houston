# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
from tests import utils
from tests.modules.sightings.resources import utils as sighting_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_asset_addition(
    db, flask_app_client, staff_user, researcher_1, request, test_root
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting

    try:
        uuids = sighting_utils.create_sighting(
            flask_app_client, researcher_1, request, test_root
        )
        sighting_id = uuids['sighting']
        new_sighting = Sighting.query.get(sighting_id)
        new_asset_group = utils.generate_asset_group_instance(researcher_1)

        with db.session.begin():
            db.session.add(new_asset_group)

        new_asset_1 = utils.generate_asset_instance(new_asset_group.guid)
        new_asset_2 = utils.generate_asset_instance(new_asset_group.guid)
        new_asset_3 = utils.generate_asset_instance(new_asset_group.guid)

        with db.session.begin():
            db.session.add(new_sighting)
            db.session.add(new_asset_group)
            db.session.add(new_asset_1)
            db.session.add(new_asset_2)
            db.session.add(new_asset_3)

        # lets try a list internally first
        assets = [new_asset_1, new_asset_2]
        new_sighting.add_assets(assets)

        assert len(new_sighting.sighting_assets) == 3

        add_asset = [
            utils.patch_add_op('assetId', '%s' % new_asset_3.guid),
        ]

        sighting_utils.patch_sighting(
            flask_app_client, researcher_1, '%s' % new_sighting.guid, add_asset
        )

        assert len(new_sighting.sighting_assets) == 4

    except AssertionError as ex:
        import tests.modules.asset_groups.resources.utils as asset_group_utils

        asset_group_utils.delete_asset_group(
            flask_app_client, staff_user, uuids['asset_group']
        )
        raise ex
