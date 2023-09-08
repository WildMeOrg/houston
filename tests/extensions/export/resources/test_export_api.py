# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import pytest

from tests.extensions.export.resources import utils as export_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.utils import (
    extension_unavailable,
    module_unavailable,
    wait_for_elasticsearch_status,
)

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    extension_unavailable('export') or module_unavailable('sightings'),
    reason='Export extension disabled, or Sighting module is disabled',
)
def test_export_api(
    flask_app,
    flask_app_client,
    admin_user,
    researcher_1,
    exporter,
    test_root,
    request,
    db,
):
    from app.modules.sightings.models import Sighting

    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    sighting_guid = uuids['sighting']
    sighting = Sighting.query.get(sighting_guid)
    sighting.index()
    wait_for_elasticsearch_status(flask_app_client, researcher_1)

    query = {'term': {'guid': sighting_guid}}
    # ok cuz admin has export priv
    resp = export_utils.export_search(flask_app_client, admin_user, query)
    assert resp.content_type == 'application/vnd.ms-excel'
    assert resp.content_length > 1000  # kind of a guess! but should be "biggish"
    # no go, cuz researcher does not have export
    export_utils.export_search(flask_app_client, researcher_1, query, 'sightings', 403)
    # ok, cuz... exporter
    resp = export_utils.export_search(flask_app_client, exporter, query)
    assert resp.content_type == 'application/vnd.ms-excel'
    export_utils.clear_files()
