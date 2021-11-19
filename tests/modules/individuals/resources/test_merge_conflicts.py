# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.asset_groups.resources import utils as ags_utils
import pytest
from tests import utils as test_utils
import logging

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
    # make sure anon gets 401
    res = individual_utils.merge_conflicts(
        flask_app_client, None, [], expected_status_code=401
    )

    # set up 2 similar individuals
    ag, sight, individual1 = ags_utils.create_asset_group_with_sighting_and_individual(
        flask_app_client,
        researcher_1,
        request,
        test_root=test_root,
    )
    ag, sight, individual2 = ags_utils.create_asset_group_with_sighting_and_individual(
        flask_app_client,
        researcher_1,
        request,
        test_root=test_root,
    )

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
        [str(individual1.guid), '0c898eb4-b913-4080-8dc5-5caefa8a1c82'],
        expected_status_code=404,
    )

    # no access to researcher_2
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_2,
        [str(individual1.guid), str(individual2.guid)],
        expected_status_code=403,
    )

    # ok, with no conflicts
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_1,
        [str(individual1.guid), str(individual2.guid)],
    )
    assert not res

    # now one with sex set
    indiv_data = {'sex': 'male'}
    ag, sight, individual3 = ags_utils.create_asset_group_with_sighting_and_individual(
        flask_app_client,
        researcher_1,
        request,
        individual_data=indiv_data,
        test_root=test_root,
    )
    res = individual_utils.merge_conflicts(
        flask_app_client,
        researcher_1,
        [str(individual1.guid), str(individual3.guid)],
    )
    assert res == ['sex']


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
):
    indiv_data = {'sex': 'male'}
    ag, sight, individual1 = ags_utils.create_asset_group_with_sighting_and_individual(
        flask_app_client,
        researcher_1,
        request,
        individual_data=indiv_data,
        test_root=test_root,
    )
    indiv_data = {'sex': 'female'}
    ag, sight, individual2 = ags_utils.create_asset_group_with_sighting_and_individual(
        flask_app_client,
        researcher_1,
        request,
        individual_data=indiv_data,
        test_root=test_root,
    )

    data = [str(individual2.guid)]
    res = individual_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        str(individual1.guid),
        data_in=data,
    )
    assert res
    assert res.get('targetId') == str(individual1.guid)
    assert res.get('targetSex') == 'male'

    # indiv1 and indiv3 male, but override merge with female
    indiv_data = {'sex': 'male'}
    ag, sight, individual3 = ags_utils.create_asset_group_with_sighting_and_individual(
        flask_app_client,
        researcher_1,
        request,
        individual_data=indiv_data,
        test_root=test_root,
    )
    data = {
        'fromIndividualIds': [str(individual1.guid)],
        'parameters': {
            'override': {'sex': 'female'},
        },
    }
    res = individual_utils.merge_individuals(
        flask_app_client,
        researcher_1,
        str(individual3.guid),
        data_in=data,
    )
    assert res
    assert res.get('targetId') == str(individual3.guid)
    assert res.get('targetSex') == 'female'
