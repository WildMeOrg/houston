# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import datetime
import time
import uuid

import pytest

from tests import utils
from tests import utils as test_utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_modify_encounter(
    db,
    flask_app_client,
    staff_user,
    researcher_1,
    researcher_2,
    admin_user,
    test_asset_group_uuid,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.modules.complex_date_time.models import ComplexDateTime, Specificities
    from app.modules.encounters.models import Encounter

    data_in = {
        'time': test_utils.isoformat_timestamp_now(),
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
        'encounters': [
            {},
            {'locationId': str(uuid.uuid4())},
        ],
    }

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )
    assert len(uuids['encounters']) == 2

    new_encounter_1 = Encounter.query.get(uuids['encounters'][0])
    assert new_encounter_1
    new_encounter_2 = Encounter.query.get(uuids['encounters'][1])
    assert new_encounter_2

    new_loc = str(uuid.uuid4())
    new_sex = 'male'
    patch_data = [
        utils.patch_replace_op('owner', str(researcher_1.guid)),
        utils.patch_replace_op('locationId', new_loc),
        utils.patch_replace_op('sex', new_sex),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_1,
        patch_data,
    )

    assert str(new_encounter_1.get_location_id()) == new_loc
    assert new_encounter_1.sex == new_sex

    # non Owner cannot make themselves the owner
    new_owner_as_res_2 = [
        utils.patch_replace_op('owner', str(researcher_2.guid)),
    ]

    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_2,
        new_owner_as_res_2,
        403,
        "You don't have the permission to access the requested resource.",
    )
    assert new_encounter_1.owner == researcher_1

    # But the owner can
    new_owner_as_res_1 = [
        utils.patch_replace_op('owner', str(researcher_2.guid)),
    ]
    enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_1, new_owner_as_res_1
    )
    assert new_encounter_1.owner == researcher_2

    # test changing locationId via patch
    new_val = str(uuid.uuid4())
    patch_data = [utils.patch_replace_op('locationId', new_val)]
    enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )

    # test setting ComplexDateTime time value
    dt = datetime.datetime.utcnow()
    dt_string = dt.isoformat()  # first test no time zone (error)
    patch_data = [
        utils.patch_replace_op('time', dt_string),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data, 409
    )
    assert 'does not have time zone' in patch_res.json['message']

    # now invalid specificity
    patch_data = [
        utils.patch_replace_op('timeSpecificity', 'fubar'),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_2,
        patch_data,
        409,
        'invalid specificity: fubar',
    )

    # invalid sex
    invalid_sex = 'something else'
    patch_data = [
        utils.patch_replace_op('sex', invalid_sex),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_2,
        patch_data,
        409,
        f'invalid sex value passed ({invalid_sex})',
    )

    # invalid taxonomy
    invalid_tax = 'not a guid'
    patch_data = [
        utils.patch_replace_op('taxonomy', invalid_tax),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_2,
        patch_data,
        409,
        f'taxonomy value passed ({invalid_tax}) is not a guid',
    )
    # should be sufficient to set a (new) time
    test_dt = '1999-01-01T12:34:56-07:00'
    patch_data = [
        utils.patch_replace_op('time', test_dt),
        utils.patch_replace_op('timeSpecificity', 'month'),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )
    test_enc = Encounter.query.get(new_encounter_1.guid)
    assert test_enc.time
    assert test_enc.time.specificity == Specificities.month
    assert test_enc.time.timezone == 'UTC-0700'
    assert test_enc.time.isoformat_in_timezone() == test_dt

    # now update just the specificity
    patch_data = [
        utils.patch_replace_op('timeSpecificity', 'day'),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )
    test_enc = Encounter.query.get(new_encounter_1.guid)
    assert test_enc.time
    assert test_enc.time.specificity == Specificities.day
    assert test_enc.time.isoformat_in_timezone() == test_dt

    # now update just the date/time
    test_dt = datetime.datetime.utcnow().isoformat() + '+03:00'
    patch_data = [
        utils.patch_replace_op('time', test_dt),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )
    test_enc = Encounter.query.get(new_encounter_1.guid)
    assert test_enc.time
    assert test_enc.time.specificity == Specificities.day
    assert test_enc.time.timezone == 'UTC+0300'
    assert test_enc.time.isoformat_in_timezone() == test_dt

    # now lets remove it!
    cdt_guid = test_enc.time_guid
    cdt = ComplexDateTime.query.get(cdt_guid)
    assert cdt
    patch_data = [
        utils.patch_remove_op('time'),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )
    test_enc = Encounter.query.get(new_encounter_1.guid)
    cdt = ComplexDateTime.query.get(cdt_guid)
    assert not test_enc.time_guid
    assert not test_enc.time
    assert not cdt

    # Check if we can sort by time
    test_dt = datetime.datetime.utcnow().isoformat() + '+03:00'
    patch_data = [
        utils.patch_replace_op('time', test_dt),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )
    test_enc = Encounter.query.get(new_encounter_1.guid)
    assert test_enc.time
    assert test_enc.time.specificity == Specificities.time
    assert test_enc.time.timezone == 'UTC+0300'
    assert test_enc.time.isoformat_in_timezone() == test_dt

    time.sleep(1)

    test_dt = datetime.datetime.utcnow().isoformat() + '+03:00'
    patch_data = [
        utils.patch_replace_op('time', test_dt),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_2.guid, researcher_1, patch_data
    )
    test_enc = Encounter.query.get(new_encounter_2.guid)
    assert test_enc.time
    assert test_enc.time.specificity == Specificities.time
    assert test_enc.time.timezone == 'UTC+0300'
    assert test_enc.time.isoformat_in_timezone() == test_dt

    from tests.modules.encounters.resources.utils import read_all_encounters_pagination

    response = read_all_encounters_pagination(
        flask_app_client, staff_user, sort='time.datetime'
    )
    actual_order = [uuid.UUID(value['guid']) for value in response.json]

    expected_order = [
        value[1]
        for value in sorted(
            (encounter.time.datetime, encounter.guid)
            for encounter in [new_encounter_1, new_encounter_2]
        )
    ]
    assert actual_order == expected_order

    test_dt = (
        new_encounter_1.time.datetime - datetime.timedelta(hours=1)
    ).isoformat() + '+03:00'
    patch_data = [
        utils.patch_replace_op('time', test_dt),
    ]
    patch_res = enc_utils.patch_encounter(
        flask_app_client, new_encounter_2.guid, researcher_1, patch_data
    )

    expected_order = [
        value[1]
        for value in sorted(
            (encounter.time.datetime, encounter.guid)
            for encounter in [new_encounter_1, new_encounter_2]
        )
    ]
    assert actual_order[::-1] == expected_order

    # Check if we can sort with elasticsearch too
    from app.extensions import elasticsearch as es

    with es.session.begin(blocking=True, verify=True):
        Encounter.index_all(force=True)

    body = {}
    _, encounters = Encounter.elasticsearch(body, total=True, sort='time.datetime')
    vals = [encounter.time.datetime for encounter in encounters]
    assert vals == sorted(vals)

    # Attach some assets and annotations
    from app.modules.asset_groups.models import AssetGroup

    assets = AssetGroup.query.get(test_asset_group_uuid).assets
    new_encounter_1.sighting.add_assets(assets)
    for asset in assets:
        annot_utils.create_annotation(
            flask_app_client, researcher_2, str(asset.guid), str(new_encounter_1.guid)
        )

    enc1_annotations = [
        {
            'asset_guid': '/api/v1/assets/src/' + str(ann.asset.guid),
            'asset_src': str(ann.asset.guid),
            'ia_class': 'test',
            'guid': str(ann.guid),
            'bounds': {'rect': [0, 1, 2, 3], 'theta': 0},
        }
        for ann in new_encounter_1.annotations
    ]

    enc1 = enc_utils.read_encounter(flask_app_client, researcher_2, new_encounter_1.guid)
    assert set(enc1.json) >= set(
        {
            'customFields': {},
            'guid': str(new_encounter_1.guid),
            'locationId': new_val,
            'created': new_encounter_1.created.isoformat() + '+00:00',
            'updated': new_encounter_1.updated.isoformat() + '+00:00',
            'owner': {
                'full_name': researcher_2.full_name,
                'guid': str(researcher_2.guid),
                'profile_fileupload': None,
            },
            'submitter': {
                'full_name': researcher_1.full_name,
                'guid': str(researcher_1.guid),
                'profile_fileupload': None,
            },
            'annotations': enc1_annotations,
            'hasEdit': True,
            'hasView': True,
        }
    )

    # Now try moving some annots from enc 1 to enc 2
    # Not an annot
    invalid_annot_guid = str(uuid.uuid4())
    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_2.guid,
        researcher_1,
        [utils.patch_add_op('annotations', invalid_annot_guid)],
        409,
        f'guid value passed ({invalid_annot_guid}) is not an annotation guid',
    )

    # try to steal annotation on an encounter owned by a researcher 2
    private_annot_guid = enc1_annotations[0]['guid']
    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_2.guid,
        researcher_1,
        [utils.patch_add_op('annotations', private_annot_guid)],
        409,
        f'annotation {private_annot_guid} owned by a different user',
    )

    # Need to make encounter 2 owned by researcher 2
    # But the owner can
    new_owner_as_res_1 = [
        utils.patch_replace_op('owner', str(researcher_2.guid)),
    ]
    enc_utils.patch_encounter(
        flask_app_client, new_encounter_2.guid, researcher_1, new_owner_as_res_1
    )
    assert new_encounter_2.owner == researcher_2

    # Now the patch should work
    owned_annot_guid = private_annot_guid
    patch_resp = enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_2.guid,
        researcher_2,
        [utils.patch_add_op('annotations', owned_annot_guid)],
    )
    assert patch_resp.json['annotations'][0]['guid'] == owned_annot_guid
    assert str(new_encounter_2.annotations[0].guid) == owned_annot_guid
    assert owned_annot_guid not in [
        str(annot.guid) for annot in new_encounter_1.annotations
    ]

    # now we test modifying customFields
    cfd_id = setting_utils.custom_field_create(
        flask_app_client, admin_user, 'test_cfd', cls='Encounter'
    )
    assert cfd_id is not None

    # test patch on customFields
    new_cfd_test_value = 'NEW_CFD_TEST_VALUE'
    patch_data = [
        utils.patch_replace_op(
            'customFields', {'id': cfd_id, 'value': new_cfd_test_value}
        )
    ]
    enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )

    # check that change was made
    enc = enc_utils.read_encounter(flask_app_client, researcher_2, new_encounter_1.guid)
    # make sure customFields value has been altered
    assert 'customFields' in enc.json
    assert cfd_id in enc.json['customFields']
    assert enc.json['customFields'][cfd_id] == new_cfd_test_value

    # some misc tests while we have all this data set up
    assert len(new_encounter_1.sighting.get_encounter_assets()) == 4
    assert len(new_encounter_1.sighting.get_all_assets()) == 5
    assert len(new_encounter_1.sighting.get_annotations()) == 4
    assert not new_encounter_1.sighting.is_migrated_data()

    new_encounter_1.sighting.delete_cascade()


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_create_encounter_time_test(
    flask_app, flask_app_client, researcher_1, request, test_root
):
    from app.modules.complex_date_time.models import Specificities
    from app.modules.encounters.models import Encounter
    from tests.modules.sightings.resources import utils as sighting_utils

    # test with invalid time
    sighting_data = {
        'encounters': [
            {
                'time': 'fubar',
            }
        ],
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'locationId': test_utils.get_valid_location_id(),
    }
    sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error='timeSpecificity field missing',
    )
    # Now TimeSpecificity, but still garbage time
    sighting_data['encounters'][0]['timeSpecificity'] = 'time'
    sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error='time field is not a valid datetime: fubar',
    )
    # now ok, but missing timezone
    sighting_data['encounters'][0]['time'] = '1999-12-31T23:59:59'
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error='timezone cannot be derived from time: 1999-12-31T23:59:59',
    )

    # getting closer; bad specificity
    sighting_data['encounters'][0]['time'] = '1999-12-31T23:59:59+03:00'
    sighting_data['encounters'][0]['timeSpecificity'] = 'fubar'
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=400,
        expected_error='timeSpecificity fubar not supported',
    )

    # finally; ok
    sighting_data['encounters'][0]['timeSpecificity'] = 'day'
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=200,
    )
    assert uuids
    test_enc = Encounter.query.get(uuids['encounters'][0])
    assert test_enc
    assert test_enc.time
    assert test_enc.time.timezone == 'UTC+0300'
    assert test_enc.time.specificity == Specificities.day
    assert test_enc.time.isoformat_in_timezone() == sighting_data['encounters'][0]['time']


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_patch(flask_app, flask_app_client, researcher_1, request, test_root):
    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    encounter_guid = uuids['encounters'][0]

    lat = utils.random_decimal_latitude()
    patch_resp = enc_utils.patch_encounter(
        flask_app_client,
        encounter_guid,
        researcher_1,
        data=[
            # valid
            {'op': 'add', 'path': '/decimalLatitude', 'value': lat},
            # invalid
            {'op': 'add', 'path': '/decimalLongitude', 'value': 999.9},
        ],
        expected_status_code=409,
    )
    assert (
        patch_resp.json['message'] == 'decimalLongitude value passed (999.9) is invalid'
    )

    new_time = test_utils.isoformat_timestamp_now()
    patch_resp = enc_utils.patch_encounter(
        flask_app_client,
        encounter_guid,
        researcher_1,
        data=[
            {'op': 'add', 'path': '/time', 'value': new_time},
            {'op': 'add', 'path': '/owner', 'value': str(uuid.uuid4())},
        ],
        expected_status_code=409,
    )
    assert 'Failed to update Encounter details.' in patch_resp.json['message']

    lat = utils.random_decimal_latitude()
    long = utils.random_decimal_longitude()
    new_time = test_utils.isoformat_timestamp_now()
    patch_resp = enc_utils.patch_encounter(
        flask_app_client,
        encounter_guid,
        researcher_1,
        data=[
            {'op': 'add', 'path': '/decimalLatitude', 'value': lat},
            {'op': 'add', 'path': '/decimalLongitude', 'value': long},
            {'op': 'add', 'path': '/time', 'value': new_time},
            {'op': 'add', 'path': '/owner', 'value': str(uuid.uuid4())},
        ],
        expected_status_code=409,
    ).json
    assert "('field_name', 'owner')]) could not succeed." in patch_resp['message']
