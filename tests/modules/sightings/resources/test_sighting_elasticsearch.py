# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

from tests import utils as test_utils
from tests.extensions.elasticsearch.resources import utils as es_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.modules.sightings.resources import utils as sighting_utils
from tests.utils import (
    elasticsearch,
    extension_unavailable,
    module_unavailable,
    wait_for_elasticsearch_status,
)

EXPECTED_KEYS = {
    'created',
    'guid',
    'updated',
    'indexed',
    'comments',
    'time',
    'timeSpecificity',
    'locationId',
    'locationId_value',
    'owners',
    'taxonomy_guids',
    'customFields',
}


# Likewise, this should work but no sighting has been indexed properly so cannot run this test
def no_test_sighting_elasticsearch_mappings(flask_app_client, researcher_1):
    # Get the response and just validate that it has the correct keys
    test_utils.get_dict_via_flask(
        flask_app_client,
        researcher_1,
        scopes='search:read',
        path=es_utils.get_mapping_path('sighting'),
        expected_status_code=200,
        response_200=EXPECTED_KEYS,
    )


@pytest.mark.skipif(
    test_utils.module_unavailable('sightings'), reason='Sightings module disabled'
)
def test_search(flask_app_client, researcher_1, request, test_root):
    from app.modules.sightings.models import Sighting

    sighting_guid = sighting_utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )['sighting']
    # Force created sighting to be indexed in elasticsearch
    Sighting.query.get(sighting_guid).index()
    wait_for_elasticsearch_status(flask_app_client, researcher_1)

    resp = test_utils.get_list_via_flask(
        flask_app_client,
        researcher_1,
        scopes='sightings:read',
        path='/api/v1/sightings/search',
        expected_status_code=200,
        expected_fields=EXPECTED_KEYS,
    )
    assert len(resp.json) == 1
    assert resp.json[0]['guid'] == str(sighting_guid)
    assert resp.headers['X-Total-Count'] == '1'
    # is -1 cuz query above was "atypical" .... meh
    assert resp.headers['X-Viewable-Count'] == '-1'

    resp = test_utils.post_via_flask(
        flask_app_client,
        researcher_1,
        scopes='sightings:read',
        path='/api/v1/sightings/search',
        data={'bool': {'filter': [], 'must_not': []}},
        expected_status_code=200,
        response_200=EXPECTED_KEYS,
        returns_list=True,
    )
    assert len(resp.json) == 1
    assert resp.json[0]['guid'] == str(sighting_guid)
    assert resp.headers['X-Total-Count'] == '1'
    assert resp.headers['X-Viewable-Count'] == '1'


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension or module disabled',
)
def test_search_with_elasticsearch(
    db, flask_app_client, researcher_1, request, test_root
):
    from app.extensions import elasticsearch as es
    from app.modules.names.models import DEFAULT_NAME_CONTEXT
    from app.modules.sightings.models import Sighting

    sighting_1_id = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': DEFAULT_NAME_CONTEXT, 'value': 'Zebra 1'},
                {'context': 'nickname', 'value': 'Nick'},
            ],
        },
    )['sighting']
    individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': 'nickname', 'value': 'Nick'},
            ],
        },
    )
    individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': 'nickname', 'value': 'Nick Jr.'},
            ],
        },
    )

    # Index all sightings
    with es.session.begin(blocking=True):
        Sighting.index_all(force=True)

    # Wait for elasticsearch to catch up
    wait_for_elasticsearch_status(flask_app_client, researcher_1)
    assert len(Sighting.elasticsearch(None, load=False)) == 3

    # Search sightings (matching GUID first)
    searchTerm = sighting_1_id
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {'term': {'guid': searchTerm}},
                {'term': {'locationId': searchTerm}},
                {
                    'query_string': {
                        'query': '*{}*'.format(searchTerm),
                        'fields': [
                            'verbatimLocality',
                            'owners.full_name',
                            'locationId_value',
                        ],
                    },
                },
            ],
        },
    }
    result_api = Sighting.elasticsearch(search, load=True)
    response = elasticsearch(flask_app_client, researcher_1, 'sightings', search)
    result_rest = response.json
    expected_fields = {
        'customFields',
        'owners',
        'guid',
        'timeSpecificity',
        'locationId',
        'locationId_value',
        'comments',
        'created',
        'updated',
        'indexed',
        'elasticsearchable',
        'submissionTime',
        'taxonomy_guids',
        'time',
        'locationId_keyword',
        'verbatimLocality',
    }
    assert len(result_api) == 1
    assert len(result_api) == len(result_rest)
    assert str(result_api[0].guid) == result_rest[0].get('guid')
    assert set(result_rest[0].keys()) >= expected_fields

    sighting = result_api[0]
    searchTerm = str(sighting.location_guid)
    all_location_ids = [str(sighting.location_guid) for sighting in Sighting.query.all()]
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {'term': {'guid': searchTerm}},
                {'term': {'locationId': searchTerm}},
                {
                    'query_string': {
                        'query': '*{}*'.format(searchTerm),
                        'fields': [
                            'verbatimLocality',
                            'owners.full_name',
                            'locationId_value',
                        ],
                    },
                },
            ],
        },
    }
    result_api = Sighting.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'sightings', search)
    result_rest = response.json
    assert len(result_api) == all_location_ids.count(searchTerm)
    assert len(result_api) == len(result_rest)
