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
    researcher_2,
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
    # researcher_1 should have access
    resp = export_utils.export_search(flask_app_client, researcher_1, query)
    assert resp.content_type == 'application/vnd.ms-excel'
    assert resp.content_length > 1000
    # researcher_2 should get 400 (no matching) cuz does not have access to sighting
    resp = export_utils.export_search(
        flask_app_client, researcher_2, query, 'sightings', 400
    )
    # TODO fix when encounters working
    # now lets test encounter export too
    # resp = export_utils.export_search(flask_app_client, admin_user, {}, 'encounters')
    # assert resp.content_type == 'application/vnd.ms-excel'
    # assert resp.content_length > 1000
    export_utils.clear_files()


@pytest.mark.skipif(
    extension_unavailable('export') or module_unavailable('sightings'),
    reason='Export extension disabled, or Sighting module is disabled',
)
def test_values(
    flask_app,
    flask_app_client,
    admin_user,
    researcher_1,
    exporter,
    test_root,
    request,
    db,
):
    import datetime

    from app.extensions.export.models import Export
    from app.modules.sightings.models import Sighting
    from tests.modules.site_settings.resources import utils as setting_utils

    cfd_string_guid = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'cfd_string', cls='Sighting'
    )
    cfd_multiple_guid = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'cfd_multiple', cls='Sighting', multiple=True
    )
    cfd_latlong_guid = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'cfd_latlong', cls='Sighting', displayType='latlong'
    )
    cfd_daterange_guid = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'cfd_daterange',
        cls='Sighting',
        multiple=True,
        displayType='daterange',
    )
    cfd_date_guid = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'cfd_date', cls='Sighting', displayType='date'
    )
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    sighting_guid = uuids['sighting']
    sighting = Sighting.query.get(sighting_guid)
    sighting.set_custom_field_value(cfd_string_guid, 'test 123')
    sighting.set_custom_field_value(cfd_multiple_guid, ['a', 'b'])
    sighting.set_custom_field_value(cfd_latlong_guid, [12.3, 34.5])
    today = datetime.datetime.now()
    tomorrow = today + datetime.timedelta(days=1)
    sighting.set_custom_field_value(cfd_daterange_guid, [today, tomorrow])
    sighting.set_custom_field_value(cfd_date_guid, today)
    export = Export()
    export.add(sighting)
    export_utils.clear_files()
