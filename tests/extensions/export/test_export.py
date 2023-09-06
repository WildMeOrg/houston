# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging

import pytest

from tests.modules.individuals.resources import utils as individual_utils
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
    from app.modules.encounters.models import Encounter
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
    enc_guid = uuids['encounters'][0]
    response = individual_utils.create_individual(
        flask_app_client, researcher_1, 200, {'encounters': [{'id': str(enc_guid)}]}
    )
    indiv_guid = response.json['guid']

    sight = Sighting.query.get(uuids['sighting'])
    sed = sight.export_data
    assert sed
    assert 'guid' in sed
    assert sed['guid'] == str(sight.guid)
    assert 'locationId' in sed
    assert 'time' in sed
    assert 'timeSpecificity' in sed
    assert f'customField.{cf_name}' in sed

    enc = Encounter.query.get(enc_guid)
    eed = enc.export_data
    assert eed
    assert 'ownerGuid' in eed
    assert 'individualGuid' in eed
    assert 'taxonomy' in eed

    indiv = Individual.query.get(indiv_guid)
    request.addfinalizer(lambda: indiv.delete())
    assert indiv
    indiv.add_name('FirstName', 'firsty', admin_user)
    indiv.add_name('test.context', 'test', admin_user)
    ied = indiv.export_data
    assert ied
    assert 'guid' in ied
    assert 'sex' in ied
    assert 'taxonomy' in ied
    assert not indiv.export_custom_fields({})
    assert 'name.FirstName' in ied
    assert ied['name.FirstName'] == 'firsty'
    assert 'name.test.context' in ied
    assert ied['name.test.context'] == 'test'

    # test that customField will now show up in export_data
    cf_name2 = 'test_cfd2'
    setting_utils.custom_field_create(
        flask_app_client, admin_user, cf_name2, cls='Individual'
    )
    ied = indiv.export_data
    assert f'customField.{cf_name2}' in ied


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
    from app.modules.names.models import Name
    from app.modules.sightings.models import Sighting

    export = Export()
    assert export.workbook
    assert not export.columns
    assert not export.sheets
    fname = export.filename
    assert fname.startswith('codex-export-Unknown-')

    indiv = Individual()
    export.add(indiv)
    assert len(export.sheets) == 1
    assert len(export.columns) == 1
    assert Individual in export.columns
    assert export.columns[Individual] == [
        'created',
        'guid',
        'sex',
        'taxonomy',
        'timeOfBirth',
        'timeOfDeath',
        'updated',
    ]

    name = Name()
    with pytest.raises(ValueError) as ve:
        export.add(name)
    assert 'is not an ExportMixin' in str(ve)

    sight = Sighting()
    export.add(sight)
    assert len(export.sheets) == 2
    assert len(export.columns) == 2

    assert not os.path.exists(export.filepath)
    saved_name = export.save()
    assert saved_name == fname
    assert os.path.exists(export.filepath)
    os.remove(export.filepath)
