# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import pytest

from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils
from tests.utils import extension_unavailable, module_unavailable

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    extension_unavailable('export') or module_unavailable('sightings'),
    reason='Export extension disabled, or Sighting module is disabled',
)
def test_export_fields(
    flask_app, flask_app_client, admin_user, researcher_1, test_root, request, db
):
    # from app.modules.encounters.models import Encounter
    from app.modules.individuals.models import Individual
    from app.modules.sightings.models import Sighting

    cf_name = 'test_cfd'
    setting_utils.custom_field_create(
        flask_app_client, admin_user, cf_name, cls='Sighting'
    )

    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    sight = Sighting.query.get(uuids['sighting'])
    sed = sight.export_data
    assert sed
    assert 'guid' in sed
    assert sed['guid'] == str(sight.guid)
    assert 'locationId' in sed
    assert 'time' in sed
    assert 'timeSpecificity' in sed
    assert f'customField.{cf_name}' in sed
    # enc = Encounter.query.get(uuids['encounters'][0])
    indiv = Individual()
    assert indiv.export_data
    assert not indiv.export_custom_fields({})


@pytest.mark.skipif(
    extension_unavailable('export'),
    reason='Export extension disabled',
)
def test_export_misc(
    flask_app, flask_app_client, admin_user, researcher_1, test_root, request, db
):
    import os

    from app.extensions.export.models import Export
    from app.modules.individuals.models import Individual
    from app.modules.sightings.models import Sighting

    export = Export()
    assert export.workbook
    assert not export.columns
    assert not export.active_class
    fname = export.filename
    assert fname.startswith('codex-export-Unknown-')

    indiv = Individual()
    export.add(indiv)
    assert export.active_class == Individual
    assert export.columns == ['created', 'guid', 'updated']

    sight = Sighting()
    with pytest.raises(ValueError) as ve:
        export.add(sight)
    assert 'does not match current worksheet class' in str(ve)

    assert not os.path.exists(export.filepath)
    saved_name = export.save()
    assert saved_name == fname
    assert os.path.exists(export.filepath)
    os.remove(export.filepath)
