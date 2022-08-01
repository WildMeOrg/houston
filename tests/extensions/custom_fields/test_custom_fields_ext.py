# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import logging
import uuid

import pytest

from app.utils import HoustonException
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils
from tests.utils import module_unavailable

log = logging.getLogger(__name__)


def test_get_definition(flask_app, flask_app_client, admin_user):
    from app.modules.site_settings.helpers import SiteSettingCustomFields

    cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'test_cfd', cls='Sighting'
    )
    assert cfd_id is not None
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert defn
    assert defn['name'] == 'test_cfd'
    assert defn['type'] == 'string'
    assert isinstance(defn['schema'], dict)

    # bad id
    defn = SiteSettingCustomFields.get_definition('Sighting', uuid.uuid4())
    assert not defn

    # wrong class (correct id)
    defn = SiteSettingCustomFields.get_definition('Encounter', cfd_id)
    assert not defn

    # bunk class
    with pytest.raises(HoustonException) as exc:
        defn = SiteSettingCustomFields.get_definition('fubar', uuid.uuid4())
    assert str(exc.value) == 'Key site.custom.customFields.fubar Not supported'


# this will not (nor ever?) be exhaustive... but try to hit big ones
def test_is_valid_value(flask_app, flask_app_client, admin_user):
    import datetime

    from app.modules.site_settings.helpers import SiteSettingCustomFields

    # simple string
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_string',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, 'test')
    assert SiteSettingCustomFields.is_valid_value(defn, '')
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 123)
    assert not SiteSettingCustomFields.is_valid_value(defn, ['test'])
    assert not SiteSettingCustomFields.is_valid_value(defn, {'foo': 'bar'})

    # string, but multiple
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_string_multiple',
        multiple=True,
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'test')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 123)
    assert SiteSettingCustomFields.is_valid_value(defn, ['test'])
    assert SiteSettingCustomFields.is_valid_value(defn, [])
    assert SiteSettingCustomFields.is_valid_value(defn, [None])  # ugh, None
    assert not SiteSettingCustomFields.is_valid_value(defn, [123])
    assert not SiteSettingCustomFields.is_valid_value(defn, {'foo': 'bar'})

    # boolean
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_boolean',
        type='boolean',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, True)
    assert SiteSettingCustomFields.is_valid_value(defn, False)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'false')
    assert not SiteSettingCustomFields.is_valid_value(defn, 123)
    assert not SiteSettingCustomFields.is_valid_value(defn, ['test'])
    assert not SiteSettingCustomFields.is_valid_value(defn, {'foo': 'bar'})

    # not going to do more tests for multiple, as the code just recurses for that
    #   and therefore should be "tested enough" by the multiple-string.  famous last words?

    # integer
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_integer',
        type='integer',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, 123)
    assert SiteSettingCustomFields.is_valid_value(defn, -123)
    assert SiteSettingCustomFields.is_valid_value(defn, 0)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 123.123)
    assert not SiteSettingCustomFields.is_valid_value(defn, 1.0)
    assert not SiteSettingCustomFields.is_valid_value(defn, 0.0)  # i dont make the rules
    assert not SiteSettingCustomFields.is_valid_value(defn, 'word')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert not SiteSettingCustomFields.is_valid_value(defn, [1, 2, 3])
    assert not SiteSettingCustomFields.is_valid_value(defn, ['test'])
    assert not SiteSettingCustomFields.is_valid_value(defn, {'foo': 'bar'})

    # double (displayType is `float`)
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_double',
        type='double',
        schema_mods={'displayType': 'float'},
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, 123.1)
    assert SiteSettingCustomFields.is_valid_value(defn, -123.2)
    assert SiteSettingCustomFields.is_valid_value(defn, 0.0)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 123)
    assert not SiteSettingCustomFields.is_valid_value(defn, 0)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'word')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert not SiteSettingCustomFields.is_valid_value(defn, [1.0, 2.0])
    assert not SiteSettingCustomFields.is_valid_value(defn, {'foo': 'bar'})

    # date
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_date',
        type='date',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    dt = datetime.datetime.utcnow()
    assert SiteSettingCustomFields.is_valid_value(defn, dt)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 123.4)
    assert not SiteSettingCustomFields.is_valid_value(defn, 0)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'word')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert not SiteSettingCustomFields.is_valid_value(defn, [dt])
    assert not SiteSettingCustomFields.is_valid_value(defn, [1.0, 2.0])
    assert not SiteSettingCustomFields.is_valid_value(defn, {'foo': 'bar'})


# returns ints based on type of failure (0 if success)
def _set_and_reset_test(db, obj, cfd_id, value):
    try:
        obj.set_custom_field_value(cfd_id, value)
    except ValueError as err:
        log.info(f'_set_and_test raised: {str(err)}')
        return 1

    val = uuid.uuid4()  # shouldnt match anything

    # first we read this way
    try:
        val = obj.get_custom_field_value(cfd_id)
    except ValueError as err:
        log.info(f'_set_and_test raised: {str(err)}')
        return 2
    if val != value:
        return 3

    # then we check this way
    if not isinstance(obj.custom_fields, dict):
        return 4
    if cfd_id not in obj.custom_fields:
        return 5
    if obj.custom_fields[cfd_id] != value:
        return 6

    # now set this way
    new_value = {cfd_id: value}
    try:
        obj.set_custom_field_values(new_value)
    except ValueError as err:
        log.info(f'_set_and_test raised: {str(err)}')
        return 7
    if obj.get_custom_field_value(cfd_id) != value:
        return 8

    # lets write to db and make sure things are cool
    with db.session.begin():
        db.session.merge(obj)
    db.session.refresh(obj)
    if obj.get_custom_field_value(cfd_id) != value:
        return 12

    # now lets test reset
    try:
        obj.reset_custom_field_value(cfd_id)
    except ValueError as err:
        log.info(f'_set_and_test raised: {str(err)}')
        return 9

    if obj.get_custom_field_value(cfd_id) is not None:
        return 10
    if cfd_id in obj.custom_fields:
        return 11

    return 0


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
# going with the idea that testing on one class is as good as any
# this wont try to test all invalid-value cases, as the above test is for that
def test_set_and_reset_values(
    flask_app, flask_app_client, admin_user, researcher_1, test_root, request, db
):
    import datetime

    from app.modules.encounters.models import Encounter
    from app.modules.sightings.models import Sighting

    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    sight = Sighting.query.get(uuids['sighting'])
    enc = Encounter.query.get(uuids['encounters'][0])

    # string
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_string_cfd',
    )
    assert _set_and_reset_test(db, sight, cfd_id, 'test') == 0
    assert _set_and_reset_test(db, sight, cfd_id, 100) == 1
    assert _set_and_reset_test(db, enc, cfd_id, 'test') == 1

    # integer, multiple
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_integer_multiple_cfd',
        type='integer',
        multiple=True,
    )
    assert _set_and_reset_test(db, sight, cfd_id, [1, 2, -3]) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 100) == 1

    # date
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_date_cfd',
        type='date',
    )
    dt = datetime.datetime.utcnow().replace(microsecond=0)
    assert _set_and_reset_test(db, sight, cfd_id, dt) == 0
    assert _set_and_reset_test(db, sight, cfd_id, None) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 1234567) == 1

    # boolean
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_boolean_cfd',
        type='boolean',
    )
    assert _set_and_reset_test(db, sight, cfd_id, True) == 0
    assert _set_and_reset_test(db, sight, cfd_id, False) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 'true') == 1
