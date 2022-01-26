# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid
from unittest import mock

from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.modules.site_settings.resources import utils as setting_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_modify_encounter(
    db,
    flask_app_client,
    researcher_1,
    researcher_2,
    admin_user,
    test_asset_group_uuid,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.modules.encounters.models import Encounter
    import datetime

    data_in = {
        'time': datetime.datetime.now().isoformat() + '+00:00',
        'timeSpecificity': 'time',
        'context': 'test',
        'locationId': 'test',
        'encounters': [
            {},
            {'locationId': 'Monster Island'},
        ],
    }
    from datetime import datetime
    from app.modules.complex_date_time.models import ComplexDateTime, Specificities

    uuids = sighting_utils.create_sighting(
        flask_app_client, researcher_1, request, test_root, data_in
    )
    assert len(uuids['encounters']) == 2

    new_encounter_1 = Encounter.query.get(uuids['encounters'][0])
    assert new_encounter_1
    new_encounter_2 = Encounter.query.get(uuids['encounters'][1])
    assert new_encounter_2

    # test that we cant mix edm/houston
    patch_data = [
        utils.patch_replace_op('owner', str(researcher_1.guid)),
        utils.patch_replace_op('locationId', 'FAIL'),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_1.guid,
        researcher_1,
        patch_data,
        400,
        'Cannot mix EDM patch paths and houston patch paths',
    )

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
    new_val = 'LOCATION_TEST_VALUE'
    patch_data = [utils.patch_replace_op('locationId', new_val)]
    enc_utils.patch_encounter(
        flask_app_client, new_encounter_1.guid, researcher_2, patch_data
    )

    # test setting ComplexDateTime time value
    dt = datetime.utcnow()
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
    test_dt = datetime.utcnow().isoformat() + '+03:00'
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
            'asset_guid': str(ann.asset.guid),
            'ia_class': 'test',
            'guid': str(ann.guid),
        }
        for ann in new_encounter_1.annotations
    ]

    enc1 = enc_utils.read_encounter(flask_app_client, researcher_2, new_encounter_1.guid)
    assert set(enc1.json) >= set(
        {
            'customFields': {},
            'guid': str(new_encounter_1.guid),
            'locationId': new_val,
            'version': new_encounter_1.version,
            'createdHouston': new_encounter_1.created.isoformat() + '+00:00',
            'updatedHouston': new_encounter_1.updated.isoformat() + '+00:00',
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
        400,
        f'guid value passed ({invalid_annot_guid}) is not an annotation guid',
    )

    # try to steal annotation on an encounter owned by a researcher 2
    private_annot_guid = enc1_annotations[0]['guid']
    enc_utils.patch_encounter(
        flask_app_client,
        new_encounter_2.guid,
        researcher_1,
        [utils.patch_add_op('annotations', private_annot_guid)],
        400,
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

    new_encounter_1.sighting.delete_cascade()


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_modify_encounter_error(
    flask_app, flask_app_client, researcher_1, request, test_root
):
    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    assert len(uuids['encounters']) == 1
    first_enc_guid = uuids['encounters'][0]

    def edm_return_500(*args, **kwargs):
        response = mock.Mock(ok=False, status_code=500)
        response.json.return_value = None
        return response

    # test edm returning 500 error
    new_val = 'LOCATION_TEST_VALUE'
    patch_data = [utils.patch_replace_op('locationId', new_val)]
    with mock.patch.object(
        flask_app.edm, 'request_passthrough', side_effect=edm_return_500
    ):
        enc_utils.patch_encounter(
            flask_app_client,
            first_enc_guid,
            researcher_1,
            patch_data,
            expected_status_code=500,
        )


@pytest.mark.skipif(module_unavailable('encounters'), reason='Encounters module disabled')
def test_create_encounter_time_test(
    flask_app, flask_app_client, researcher_1, request, test_root
):
    from tests.modules.sightings.resources import utils as sighting_utils
    from app.modules.encounters.models import Encounter
    from app.modules.complex_date_time.models import Specificities

    # test with invalid time
    sighting_data = {
        'encounters': [
            {
                'time': 'fubar',
            }
        ],
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'locationId': 'test',
    }
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=200,
        commit_expected_status_code=400,
    )

    # now ok, but missing timezone
    sighting_data['encounters'][0]['time'] = '1999-12-31T23:59:59'
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=200,
        commit_expected_status_code=400,
    )

    # timezone included, but no specificity
    sighting_data['encounters'][0]['time'] = '1999-12-31T23:59:59+03:00'
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=200,
        commit_expected_status_code=400,
    )

    # getting closer; bad specificity
    sighting_data['encounters'][0]['timeSpecificity'] = 'fubar'
    uuids = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
        expected_status_code=200,
        commit_expected_status_code=400,
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

    # now test dict-value version
    test_dt_str = '2000-01-01T01:02:03'
    del sighting_data['encounters'][0]['timeSpecificity']
    sighting_data['encounters'][0]['time'] = {
        'datetime': test_dt_str,
        'timezone': 'US/Eastern',
        'specificity': 'month',
    }
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
    assert test_enc.time.specificity == Specificities.month
    assert test_enc.time.isoformat_utc() == test_dt_str

    # now list/components
    sighting_data['encounters'][0]['time'] = {
        'components': [2021, 12],
        'timezone': 'US/Mountain',
        # specificity should be deduced as month
    }
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
    assert test_enc.time.specificity == Specificities.month
    assert test_enc.time.isoformat_utc().startswith('2021-12-01T')
