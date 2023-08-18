# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging

import pytest

from tests import utils as test_utils

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_get_conflicts(
    db,
    flask_app_client,
    researcher_1,
    researcher_2,
    request,
    test_root,
):
    from app.modules.individuals.models import Individual
    from tests.modules.individuals.resources import utils as individual_utils

    request.addfinalizer(lambda: test_utils.cleanup_autogen())
    # make sure anon gets 401
    res = individual_utils.merge_conflicts(
        flask_app_client, None, [], expected_status_code=401
    )

    # set up 2 similar individuals
    individual1_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual2_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )
    individual1_guid = individual1_uuids['individual']
    individual2_guid = individual2_uuids['individual']

    # bunk individual data
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_2,
        [],
        expected_status_code=500,
    )

    # unknown individual guid
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_2,
        [individual1_guid, '0c898eb4-b913-4080-8dc5-5caefa8a1c82'],
        expected_status_code=404,
    )

    # no access to researcher_2
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_2,
        [individual1_guid, individual2_guid],
        expected_status_code=403,
    )

    # ok, with no conflicts
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_1,
        [individual1_guid, individual2_guid],
    )
    assert not len(res)

    # now one with sex set
    indiv_data = {'sex': 'male'}
    individual3_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=indiv_data,
    )
    individual3_guid = individual3_uuids['individual']
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_1,
        [individual1_guid, individual3_guid],
    )
    assert res == {'sex': True}

    # add some names with a common context
    individual1 = Individual.query.get(individual1_guid)
    individual2 = Individual.query.get(individual2_guid)
    assert individual1
    assert individual2
    shared_context = 'test-context'
    individual1.add_name(shared_context, 'name1', researcher_1)
    individual2.add_name(shared_context, 'name2', researcher_1)
    individual2.add_name('a different context', 'nameX', researcher_1)
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_1,
        [individual1_guid, individual2_guid],
    )
    assert 'name_contexts' in res
    assert len(res['name_contexts']) == 1
    assert res['name_contexts'][0] == shared_context


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
def test_overrides(
    db,
    flask_app_client,
    researcher_1,
    researcher_2,
    request,
    test_root,
    admin_user,
):
    import tests.modules.site_settings.resources.utils as setting_utils
    from app.modules.individuals.models import Individual
    from tests.modules.individuals.resources import utils as individual_utils

    request.addfinalizer(lambda: test_utils.cleanup_autogen())
    indiv1_data = {'sex': 'male'}
    individual1_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=indiv1_data,
    )
    indiv2_data = {'sex': 'female'}
    individual2_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=indiv2_data,
    )
    individual1_guid = individual1_uuids['individual']
    individual2_guid = individual2_uuids['individual']

    data = [individual2_guid]
    res = individual_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        individual1_guid,
        data_in=data,
    )
    assert res
    assert res.get('targetId') == individual1_guid
    assert res.get('targetSex') == 'male'

    # indiv1 and indiv3 male, but override merge with female
    indiv3_data = {'sex': 'male'}
    individual3_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=indiv3_data,
    )
    individual3_guid = individual3_uuids['individual']
    data = {
        'fromIndividualIds': [individual1_guid],
        'parameters': {
            'override': {'sex': 'female'},
        },
    }
    res = individual_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        individual3_guid,
        data_in=data,
    )
    assert res
    assert res.get('targetId') == individual3_guid
    assert res.get('targetSex') == 'female'
    indivs = Individual.query.all()
    assert len(indivs) == 1
    tx1_guid = str(indivs[0].taxonomy_guid)

    # test overrides dealing with AutogeneratedNames
    agn1_prefix = 'FOO'
    agn2_prefix = 'BAR'
    vals = [
        {
            'id': tx1_guid,
            'commonNames': ['Example'],
            'scientificName': 'Exempli gratia',
            'itisTsn': -1234,
            'autogeneratedName': {
                'prefix': agn1_prefix,
                'type': 'auto_species',
                'enabled': True,
            },
        },
        {
            'commonNames': ['Example'],
            'scientificName': 'Exempli gratia deux',
            'itisTsn': -1235,
            'autogeneratedName': {
                'prefix': agn2_prefix,
                'type': 'auto_species',
                'enabled': True,
            },
        },
    ]
    rtn = setting_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        vals,
        'site.species',
    )
    tx2_guid = rtn.json['value'][1]['id']
    # this should have been automagically added
    assert indivs[0].names[0].value_resolved == 'FOO-001'

    indiv4_data = {'taxonomy': tx2_guid}
    individual4_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=indiv4_data,
    )
    individual4_guid = individual4_uuids['individual']

    # merge indiv3 into indiv4 but using incompatible autogen-name (400 response)
    data = {
        'fromIndividualIds': [individual3_guid],
        'parameters': {
            'override': {
                'name_context': {indivs[0].names[0].context: str(indivs[0].names[0].guid)}
            }
        },
    }
    res = individual_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        individual4_guid,
        data_in=data,
        expected_status_code=400,
    )
    assert (
        res['message']
        == 'override results in incompatible AutogeneratedName and Taxonomy'
    )
    indiv4 = Individual.query.get(individual4_guid)
    # this should be okay
    data['parameters']['override']['name_context'] = {
        indiv4.names[0].context: str(indiv4.names[0].guid)
    }
    res = individual_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        individual4_guid,
        data_in=data,
    )


@pytest.mark.skipif(
    test_utils.module_unavailable('individuals', 'encounters', 'sightings'),
    reason='Individuals module disabled',
)
# this is so messy it deserves its own test
def test_merge_names(
    db,
    flask_app_client,
    researcher_1,
    researcher_2,
    request,
    test_root,
    admin_user,
):
    import tests.modules.site_settings.resources.utils as setting_utils
    from app.modules.individuals.models import Individual
    from tests.modules.individuals.resources import utils as individual_utils

    request.addfinalizer(lambda: test_utils.cleanup_autogen())
    indiv1_data = {'sex': 'male'}
    individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=indiv1_data,
    )
    indiv2_data = {'sex': 'female'}
    individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=indiv2_data,
    )

    indivs = Individual.query.all()
    tx1_guid = str(indivs[0].taxonomy_guid)

    # test overrides dealing with AutogeneratedNames
    agn1_prefix = 'FOO'
    agn2_prefix = 'BAR'
    vals = [
        {
            'id': tx1_guid,
            'commonNames': ['Example'],
            'scientificName': 'Exempli gratia',
            'itisTsn': -1234,
            'autogeneratedName': {
                'prefix': agn1_prefix,
                'type': 'auto_species',
                'enabled': True,
            },
        },
        {
            'commonNames': ['Example'],
            'scientificName': 'Exempli gratia deux',
            'itisTsn': -1235,
            'autogeneratedName': {
                'prefix': agn2_prefix,
                'type': 'auto_species',
                'enabled': True,
            },
        },
    ]
    rtn = setting_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        vals,
        'site.species',
    )
    assert rtn
    tx2_guid = rtn.json['value'][1]['id']

    # now at this point, both have same taxonomy
    assert indivs[0].names[0].value_resolved == f'{agn1_prefix}-001'
    assert indivs[1].names[0].value_resolved == f'{agn1_prefix}-002'

    mc_res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_1,
        [str(indivs[0].guid), str(indivs[1].guid)],
    )
    assert 'name_contexts' in mc_res
    assert indivs[0].names[0].context in mc_res['name_contexts']

    # we dont really do merging cuz we only wanna test merge_names() here
    override = {
        'bad_context': 'fubar',
    }
    indivs[0].merge_names([indivs[1]], override, fail_on_conflict=True)
    assert indivs[0].names[0].value_resolved == f'{agn1_prefix}-001'
    assert indivs[0].names[1].context == 'Historical Codex ID'
    assert indivs[0].names[1].value == f'{agn1_prefix}-002'

    # now we get override to favor second individual autogen name
    override = {
        indivs[0].names[0].context: str(indivs[1].names[0].guid),
    }
    indivs[0].merge_names([indivs[1]], override, fail_on_conflict=True)
    assert (
        indivs[0].names[0].value_resolved == f'{agn1_prefix}-002'
    )  # 002 won, via override
    # names[1] is holdover from previous, hence our ID1 here
    assert indivs[0].names[2].context == 'Historical Codex ID1'
    assert indivs[0].names[2].value == f'{agn1_prefix}-001'  # 001 becomes historical now

    override = {
        'autogen-00000000-1e0a-4bd1-8c94-000000000000': '00000000-d86a-410e-ba1c-000000000000',
    }
    with pytest.raises(ValueError) as verr:
        indivs[0].merge_names([indivs[1]], override, fail_on_conflict=True)
    assert 'invalid name guid' in str(verr.value)

    # try to override with name that doesnt match taxonomy
    indivs[1].taxonomy_guid = tx2_guid
    indivs[1].update_autogen_names(admin_user, 'auto_species')
    indivs[0].names[0].context != indivs[1].names[0].context  # diff species now
    override = {
        indivs[0].names[0].context: indivs[1].names[0].guid,
    }
    with pytest.raises(ValueError) as verr:
        indivs[0].merge_names([indivs[1]], override, fail_on_conflict=True)
    assert 'but does not match individual.taxonomy' in str(verr.value)
