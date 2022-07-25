# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

from tests.modules.sightings.resources import utils as sighting_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_taxonomy(
    db,
    flask_app_client,
    researcher_1,
    request,
    test_root,
    staff_user,
):
    import tests.modules.site_settings.resources.utils as site_setting_utils
    from app.modules.sightings.models import Sighting
    from app.modules.site_settings.models import Taxonomy

    try:
        uuids = sighting_utils.create_sighting(
            flask_app_client, researcher_1, request, test_root
        )
        sighting_id = uuids['sighting']
        sighting = Sighting.query.get(sighting_id)
        assert sighting is not None

        conf_tx = site_setting_utils.get_some_taxonomy_dict(flask_app_client, staff_user)
        tx = Taxonomy(conf_tx['id'])
        sighting.set_taxonomies([tx])
        assert len(sighting.get_taxonomies()) == 1
        assert sighting.get_taxonomies()[0].guid == tx.guid
        sighting.set_taxonomies([])
        assert len(sighting.get_taxonomies()) == 0
        sighting.add_taxonomy(tx)
        assert len(sighting.get_taxonomies()) == 1
        assert sighting.get_taxonomies()[0].guid == tx.guid

    except AssertionError as ex:
        sighting_utils.cleanup_sighting(flask_app_client, researcher_1, uuids)
        raise ex
