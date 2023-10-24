# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from tests.modules.site_settings.resources import utils as conf_utils
from tests.utils import extension_unavailable, module_unavailable


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_read_sentry_dsn(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    # This is the one 'lone' field that the frontend reads in isolation.
    sentry_dsn_val = conf_utils.read_main_settings(
        flask_app_client, researcher_1, 'sentryDsn'
    ).json
    assert 'value' in sentry_dsn_val


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_read_site_settings(flask_app_client, researcher_1):
    # pylint: disable=invalid-name
    conf_utils.read_main_settings(flask_app_client, researcher_1, 'site.name')

    from app.modules.ia_config_reader import IaConfig

    ia_config_reader = IaConfig()
    species = ia_config_reader.get_configured_species()
    config_response = conf_utils.read_main_settings(flask_app_client, researcher_1)
    suggested_vals = config_response.json['site.species']['suggestedValues']
    assert len(suggested_vals) >= len(species)
    for i in range(len(species)):
        assert suggested_vals[i]['scientificName'] == species[len(species) - i - 1]


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_alter_settings(flask_app_client, admin_user, db):
    from app.modules.individuals.models import Individual

    response = conf_utils.read_main_settings(flask_app_client, admin_user)
    assert 'value' in response.json['site.species']
    vals = response.json['site.species']['value']
    vals.append({'commonNames': ['Test data'], 'scientificName': 'Testus datum'})
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        vals,
        'site.species',
    )
    response = conf_utils.read_main_settings(flask_app_client, admin_user)
    assert 'value' in response.json['site.species']

    assert response.json['site.species']['value'][-1]['scientificName'] == 'Testus datum'
    # restore original list
    vals.pop()
    response = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        vals,
        'site.species',
    )

    # create a faux individual with random taxonomy_guid to test failing update site.species without it
    indiv = Individual()
    indiv.taxonomy_guid = '00000000-eb82-471e-b3be-000000000000'
    with db.session.begin():
        db.session.add(indiv)
    with pytest.raises(ValueError) as ve:
        response = conf_utils.modify_main_settings(
            flask_app_client,
            admin_user,
            vals,
            'site.species',
        )
    assert 'Missing taxonomies' in str(ve)
    with db.session.begin():
        db.session.delete(indiv)


# TODO sort this out as part of DEX 1306
#      note: some of this may have been picked up by test_alter_custom_field_categories() below
#        and others by tests/extensions/custom_fields/test_custom_fields_ext.py
@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_alter_edm_custom_fields(flask_app_client, admin_user):

    categories = conf_utils.read_main_settings(
        flask_app_client,
        admin_user,
    ).json['site.custom.customFieldCategories']
    assert 'value' in categories
    cats = categories['value']
    cats.append(
        {
            'label': 'sighting_category 1',
            'id': '252ef07f-252d-495c-ab97-4e9a15cd9aa7',
            'type': 'sighting',
            'timeCreated': 1649764520424,
            'required': 'false',
        }
    )
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        cats,
        'site.custom.customFieldCategories',
    )

    occ_cf_rsp = conf_utils.read_main_settings(flask_app_client, admin_user).json[
        'site.custom.customFields.Sighting'
    ]

    assert 'value' in occ_cf_rsp
    occ_cfs = occ_cf_rsp['value']
    if occ_cfs == []:
        occ_cfs = {}
    if 'definitions' not in occ_cfs:
        occ_cfs['definitions'] = []

    occ_cfs['definitions'].append(
        {
            'default': 'woo',
            'id': str(uuid.uuid4()),
            'multiple': False,
            'name': 'field_name',
            'required': False,
            'schema': {
                'category': '252ef07f-252d-495c-ab97-4e9a15cd9aa7',
                'description': 'wibble de woo',
                'displayType': 'string',
                'label': 'Wibble',
            },
            'timeCreated': 1649765490770,
            'type': 'string',
        }
    )
    occ_cfs['definitions'].append(
        {
            'default': 'wobble',
            'id': str(uuid.uuid4()),
            'multiple': False,
            'name': 'field_name',
            'required': False,
            'schema': {
                'category': '252ef07f-252d-495c-ab97-4e9a15cd9aa7',
                'description': "They don't fall down",
                'displayType': 'string',
                'label': 'Weeble',
            },
            'timeCreated': 1649765490770,
            'type': 'string',
        }
    )

    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        occ_cfs,
        'site.custom.customFields.Sighting',
    )
    occ_cf_rsp = conf_utils.read_main_settings(
        flask_app_client,
        admin_user,
    ).json['site.custom.customFields.Sighting']
    defaults = [
        definit['default']
        for definit in occ_cf_rsp['value']['definitions']
        if 'default' in definit
    ]
    assert 'woo' in defaults
    assert 'wobble' in defaults

    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        cats,
        'site.custom.customFieldCategories',
    )
    first = occ_cf_rsp['value']['definitions'].pop(0)
    second = occ_cf_rsp['value']['definitions'].pop(0)

    conf_utils.delete_main_setting(
        flask_app_client, admin_user, f'site.custom.customFields.Sighting/{first["id"]}'
    )
    # Try via the patch API too
    patch_data = [
        {
            'op': 'remove',
            'path': f'site.custom.customFields.Sighting/{second["id"]}',
        },
    ]
    conf_utils.patch_main_setting(
        flask_app_client,
        admin_user,
        patch_data,
    )
    # check if they're gone
    sight_cf_rsp = conf_utils.read_main_settings(
        flask_app_client,
        admin_user,
    ).json['site.custom.customFields.Sighting']

    definitions = sight_cf_rsp['value']['definitions']
    def_ids = [defi['id'] for defi in definitions]
    assert first['id'] not in def_ids
    assert second['id'] not in def_ids


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_alter_custom_field_categories(flask_app_client, admin_user):
    conf_utils.custom_field_create(
        flask_app_client, admin_user, 'test_cfd', cls='Sighting'
    )
    categories = conf_utils.read_main_settings(
        flask_app_client,
        admin_user,
    ).json['site.custom.customFieldCategories']
    assert 'value' in categories
    cats = categories['value']
    assert cats[0]['label'] == 'distance'

    # label change should be fine
    cats[0]['label'] = 'constitution'
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        cats,
        'site.custom.customFieldCategories',
    )
    categories = conf_utils.read_main_settings(
        flask_app_client,
        admin_user,
    ).json['site.custom.customFieldCategories']
    assert 'value' in categories
    cats = categories['value']
    assert cats[0]['label'] == 'constitution'

    # type change should not, however (as this category is in use)
    cats[0]['type'] = 'encounter'
    res = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        cats,
        'site.custom.customFieldCategories',
        400,
    )
    assert 'cannot modify an existing category type' in res.json['message']

    # try to add a bunk type
    cats[0]['type'] = 'sighting'
    cats.append({'id': str(uuid.uuid4()), 'label': 'why not?', 'type': 'bunky'})
    res = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        cats,
        'site.custom.customFieldCategories',
        400,
    )
    assert 'includes invalid type' in res.json['message']

    # now lets make cats[1] good so we can delete it without problem (no definitions using it)
    cats[1]['type'] = 'encounter'
    res = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        cats,
        'site.custom.customFieldCategories',
    )
    categories = conf_utils.read_main_settings(
        flask_app_client,
        admin_user,
    ).json['site.custom.customFieldCategories']
    assert 'value' in categories
    cats = categories['value']
    assert len(cats) == 2
    cats.pop()  # remove this one, should be fine (unused)
    res = conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        cats,
        'site.custom.customFieldCategories',
    )
    categories = conf_utils.read_main_settings(
        flask_app_client,
        admin_user,
    ).json['site.custom.customFieldCategories']
    assert 'value' in categories
    cats = categories['value']
    assert len(cats) == 1


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_dict_write(flask_app_client, admin_user, regular_user):
    # Create json site setting
    import uuid

    data = [
        {'guid': str(uuid.uuid4()), 'label': 'Matriarch', 'multipleInGroup': False},
        {'guid': str(uuid.uuid4()), 'label': 'IrritatingGit', 'multipleInGroup': True},
    ]

    conf_utils.modify_main_settings(
        flask_app_client, regular_user, data, 'social_group_roles', 403
    )
    resp = conf_utils.modify_main_settings(
        flask_app_client, admin_user, data, 'social_group_roles'
    )

    assert resp.json['key'] == 'social_group_roles'
    conf_utils.delete_main_setting(
        flask_app_client, regular_user, 'social_group_roles', 403
    )

    conf_utils.delete_main_setting(flask_app_client, admin_user, 'social_group_roles')


@pytest.mark.skipif(
    module_unavailable('site_settings'), reason='Site-settings module disabled'
)
def test_alter_houston_settings(flask_app_client, admin_user, researcher_1):

    username = 'noone@nowhere.com'
    password = 'VeryPrivateThing'
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        username,
        'email_service_username',
    )
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        password,
        'email_service_password',
    )
    admin_configuration = conf_utils.read_main_settings(flask_app_client, admin_user).json
    researcher_configuration = conf_utils.read_main_settings(
        flask_app_client, researcher_1
    ).json

    # admin should be able to see uname & pass, researcher should not.
    assert admin_configuration['email_service_username']['canView']
    assert admin_configuration['email_service_username']['value'] == username
    assert admin_configuration['email_service_password']['canView']
    assert admin_configuration['email_service_password']['value'] == password

    assert 'email_service_username' in researcher_configuration
    assert not researcher_configuration['email_service_username']['canView']
    assert 'value' not in researcher_configuration['email_service_username'].keys()
    assert 'email_service_password' in researcher_configuration
    assert not researcher_configuration['email_service_password']['canView']
    assert 'value' not in researcher_configuration['email_service_password'].keys()

    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        None,
        'email_service_username',
    )
    conf_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        None,
        'email_service_password',
    )
    config_response_admin = conf_utils.read_main_settings(flask_app_client, admin_user)
    admin_configuration = config_response_admin.json

    assert admin_configuration['email_service_username']['value'] is None
    assert admin_configuration['email_service_password']['value'] is None
