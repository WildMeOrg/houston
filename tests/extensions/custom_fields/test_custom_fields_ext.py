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


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_get_definition(flask_app, flask_app_client, admin_user):
    from app.modules.site_settings.helpers import SiteSettingCustomFields

    cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'test_cfd', cls='Sighting'
    )
    assert cfd_id is not None
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert defn
    assert defn['name'] == 'test_cfd'
    assert isinstance(defn['schema'], dict)
    assert defn['schema']['displayType'] == 'string'

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
@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_is_valid_value(flask_app, flask_app_client, admin_user, db):
    import datetime

    from app.modules.individuals.models import Individual
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

    # select, but missing choices
    res = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_select',
        displayType='select',
        expected_status_code=400,
    )
    assert 'choices is required' in res.json['message']
    # select, but missing choices not dicts
    res = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_select',
        displayType='select',
        schema_mods={'choices': ['a', 'b', 'c']},
        expected_status_code=400,
    )
    assert 'is not a dict' in res.json['message']
    # select, choices invalid dicts
    res = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_select',
        displayType='select',
        schema_mods={
            'choices': [{'foo': 0, 'bar': 1}],
        },
        expected_status_code=400,
    )
    assert 'missing label' in res.json['message']
    # select, choices has duplicate value
    res = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_select',
        displayType='select',
        schema_mods={
            'choices': [{'label': 'A', 'value': 'a'}, {'label': 'B', 'value': 'a'}],
        },
        expected_status_code=400,
    )
    assert 'duplicate value' in res.json['message']
    # select, should work
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_select',
        displayType='select',
        schema_mods={
            'choices': [{'label': 'A', 'value': 'a'}, {'label': 'B', 'value': 'b'}],
        },
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'test')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert SiteSettingCustomFields.is_valid_value(defn, 'b')

    # multiselect
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_multiselect',
        displayType='multiselect',
        multiple=True,
        schema_mods={
            'choices': [{'label': 'A', 'value': 'a'}, {'label': 'B', 'value': 'b'}],
        },
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'test')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert not SiteSettingCustomFields.is_valid_value(defn, ['c'])
    assert SiteSettingCustomFields.is_valid_value(defn, ['b'])
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert SiteSettingCustomFields.is_valid_value(defn, [])

    # multiselect, but required
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_multiselect_required',
        displayType='multiselect',
        required=True,
        multiple=True,
        schema_mods={
            'choices': [{'label': 'A', 'value': 'a'}, {'label': 'B', 'value': 'b'}],
        },
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'test')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert not SiteSettingCustomFields.is_valid_value(defn, ['c'])
    assert SiteSettingCustomFields.is_valid_value(defn, ['b'])
    assert not SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, [])

    # boolean
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_boolean',
        displayType='boolean',
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
        displayType='integer',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, 123)
    assert SiteSettingCustomFields.is_valid_value(defn, -123)
    assert SiteSettingCustomFields.is_valid_value(defn, 0)
    assert SiteSettingCustomFields.is_valid_value(defn, '123')
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 123.123)
    assert not SiteSettingCustomFields.is_valid_value(defn, '123.123')
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
        displayType='float',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, 123.1)
    assert SiteSettingCustomFields.is_valid_value(defn, -123.2)
    assert SiteSettingCustomFields.is_valid_value(defn, '-123.2')
    assert SiteSettingCustomFields.is_valid_value(defn, 123)
    assert SiteSettingCustomFields.is_valid_value(defn, 0.0)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    #   we now allow ints to be cast as floats.  sorrynotsorry
    # assert not SiteSettingCustomFields.is_valid_value(defn, 123)
    # assert not SiteSettingCustomFields.is_valid_value(defn, 0)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'word')
    assert not SiteSettingCustomFields.is_valid_value(defn, '')
    assert not SiteSettingCustomFields.is_valid_value(defn, [1.0, 2.0])
    assert not SiteSettingCustomFields.is_valid_value(defn, {'foo': 'bar'})

    # date
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_date',
        displayType='date',
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

    # daterange
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_daterange',
        displayType='daterange',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    dt_old = datetime.datetime.fromtimestamp(0)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 1234)
    assert not SiteSettingCustomFields.is_valid_value(defn, dt)
    assert not SiteSettingCustomFields.is_valid_value(defn, [])
    assert not SiteSettingCustomFields.is_valid_value(defn, [dt_old, dt, dt])
    assert not SiteSettingCustomFields.is_valid_value(defn, [dt, dt_old])
    assert SiteSettingCustomFields.is_valid_value(defn, [dt_old, dt])

    # latlong
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_latlong',
        displayType='latlong',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, [])
    assert not SiteSettingCustomFields.is_valid_value(defn, ['a', 'b'])
    assert not SiteSettingCustomFields.is_valid_value(defn, [100, 80])
    assert SiteSettingCustomFields.is_valid_value(defn, [80, 100])
    assert SiteSettingCustomFields.is_valid_value(defn, [0.123, -0.456])

    # individual
    indiv = Individual()
    with db.session.begin():
        # kinda shocking this works, but okay....
        db.session.merge(indiv)
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_indiv',
        displayType='individual',
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert SiteSettingCustomFields.is_valid_value(defn, None)
    assert not SiteSettingCustomFields.is_valid_value(defn, 'invalid-guid')
    assert not SiteSettingCustomFields.is_valid_value(
        defn, '00000000-dead-2170-0000-000000000000'
    )
    assert SiteSettingCustomFields.is_valid_value(defn, indiv.guid)
    assert SiteSettingCustomFields.is_valid_value(defn, str(indiv.guid))
    indiv = Individual.query.get(indiv.guid)
    db.session.delete(indiv)

    # TODO these need tests when their day comes
    # 'specifiedTime': dict,  # { time: datetime, timeSpecificity: string (ComplexDateTime.specificities) }
    # 'locationId': guid,
    # 'file': guid,  # FileUpload guid, DEX-1261


# returns ints based on type of failure (0 if success)
@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
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

    # raw id check
    if not isinstance(obj.custom_fields, dict):
        return 4
    if cfd_id not in obj.custom_fields:
        return 5
    # we cant compare this way due to serialization :(
    # if obj.custom_fields[cfd_id] != value:
    # return 6

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
    from app.modules.individuals.models import Individual
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

    # select (not required)
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_select_cfd',
        displayType='select',
        schema_mods={
            'choices': [{'label': 'A', 'value': 'a'}, {'label': 'B', 'value': 'b'}],
        },
    )
    assert _set_and_reset_test(db, sight, cfd_id, 'a') == 0
    assert _set_and_reset_test(db, sight, cfd_id, None) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 'c') == 1

    # select (required)
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_select_required_cfd',
        displayType='select',
        required=True,
        schema_mods={
            'choices': [{'label': 'A', 'value': 'a'}, {'label': 'B', 'value': 'b'}],
        },
    )
    assert _set_and_reset_test(db, sight, cfd_id, 'a') == 0
    assert _set_and_reset_test(db, sight, cfd_id, None) == 1
    assert _set_and_reset_test(db, sight, cfd_id, 'c') == 1

    # select (required, but None in choices)
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_select_required_nullchoice_cfd',
        displayType='select',
        required=True,
        schema_mods={
            'choices': [
                {'label': 'A', 'value': 'a'},
                {'label': 'B', 'value': 'b'},
                {'label': 'NONE', 'value': None},
            ],
        },
    )
    assert _set_and_reset_test(db, sight, cfd_id, 'a') == 0
    assert _set_and_reset_test(db, sight, cfd_id, None) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 'c') == 1

    # integer, multiple
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_integer_multiple_cfd',
        displayType='integer',
        multiple=True,
    )
    assert _set_and_reset_test(db, sight, cfd_id, [1, 2, -3]) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 100) == 1

    # date
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_date_cfd',
        displayType='date',
    )
    dt = datetime.datetime.utcnow().replace(microsecond=0)
    assert _set_and_reset_test(db, sight, cfd_id, dt) == 0
    assert _set_and_reset_test(db, sight, cfd_id, None) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 1234567) == 1

    # date, multiple
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_date_cfd_multiple',
        displayType='date',
        multiple=True,
    )
    dt_old = datetime.datetime.fromtimestamp(0)
    assert _set_and_reset_test(db, sight, cfd_id, [dt]) == 0
    assert _set_and_reset_test(db, sight, cfd_id, None) == 0
    assert _set_and_reset_test(db, sight, cfd_id, [dt, dt_old, dt, dt_old]) == 0
    assert _set_and_reset_test(db, sight, cfd_id, [dt, 1234]) == 1

    # boolean
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_boolean_cfd',
        displayType='boolean',
    )
    assert _set_and_reset_test(db, sight, cfd_id, True) == 0
    assert _set_and_reset_test(db, sight, cfd_id, False) == 0
    assert _set_and_reset_test(db, sight, cfd_id, 'true') == 1

    # daterange
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_daterange',
        displayType='daterange',
        multiple=True,
    )
    assert _set_and_reset_test(db, sight, cfd_id, [dt_old, dt]) == 0

    # latlong
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_latlong',
        displayType='latlong',
    )
    assert _set_and_reset_test(db, sight, cfd_id, [0.001, 120]) == 0
    assert _set_and_reset_test(db, sight, cfd_id, [333, 444]) == 1
    assert _set_and_reset_test(db, sight, cfd_id, [None, None]) == 0
    assert _set_and_reset_test(db, sight, cfd_id, [0, 0]) == 0

    # individual
    indiv = Individual()
    with db.session.begin():
        db.session.merge(indiv)
    cfd_id = setting_utils.custom_field_create(
        flask_app_client,
        admin_user,
        'test_cfd_indiv',
        displayType='individual',
    )
    assert _set_and_reset_test(db, sight, cfd_id, indiv.guid) == 0
    indiv = Individual.query.get(indiv.guid)
    db.session.delete(indiv)


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_definition_manipulation(flask_app, flask_app_client, admin_user):
    from app.modules.site_settings.helpers import SiteSettingCustomFields
    from app.modules.site_settings.models import SiteSetting

    # remove via the method
    cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'test1', cls='Sighting'
    )
    assert cfd_id is not None
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert defn
    SiteSettingCustomFields.remove_definition('Sighting', cfd_id)
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert not defn
    data = SiteSetting.get_value('site.custom.customFields.Sighting')
    assert 'definitions' in data
    assert len(data['definitions']) == 0

    # now lets add one and remove it via the special patch from DEX-1337
    cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'test2', cls='Sighting'
    )
    assert cfd_id is not None
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert defn
    setting_utils.patch_main_setting(
        flask_app_client,
        admin_user,
        [
            {
                'path': 'site.custom.customFields.Sighting/' + cfd_id,
                'op': 'remove',
            }
        ],
    )
    defn = SiteSettingCustomFields.get_definition('Sighting', cfd_id)
    assert not defn
