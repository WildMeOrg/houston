# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import pytest

from tests.modules.individuals.resources import utils as individual_utils
from tests.utils import (
    elasticsearch,
    extension_unavailable,
    module_unavailable,
    wait_for_elasticsearch_status,
)


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension or module disabled',
)
def test_search_with_elasticsearch(
    db, flask_app_client, researcher_1, request, test_root
):
    from app.extensions import elasticsearch as es
    from app.modules.individuals.models import Individual
    from app.modules.names.models import DEFAULT_NAME_CONTEXT

    individual_1_id = individual_utils.create_individual_and_sighting(
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
    )['individual']
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

    # Index all individuals
    with es.session.begin(blocking=True):
        Individual.index_all(force=True)

    # Wait for elasticsearch to catch up
    wait_for_elasticsearch_status(flask_app_client, researcher_1)
    assert len(Individual.elasticsearch(None, load=False)) == 3

    # Search individuals (matching GUID first)
    searchTerm = individual_1_id
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {'term': {'guid': searchTerm}},
                {
                    'query_string': {
                        'query': '*{}*'.format(searchTerm),
                        'fields': ['adoptionName', 'firstName'],
                    },
                },
            ],
        },
    }
    result_api = Individual.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'individuals', search)
    result_rest = response.json
    assert len(result_api) == 1
    assert len(result_api) == len(result_rest)
    assert str(result_api[0]) == result_rest[0].get('guid')

    # Search individuals (matching GUID only)
    searchTerm = individual_1_id
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {'term': {'guid': searchTerm}},
            ],
        },
    }
    result_api = Individual.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'individuals', search)
    result_rest = response.json
    assert len(result_api) == 1
    assert len(result_api) == len(result_rest)
    assert str(result_api[0]) == result_rest[0].get('guid')

    # Search individuals (shouldn't match anything)
    searchTerm = individual_1_id
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {
                    'query_string': {
                        'query': '*{}*'.format(searchTerm),
                        'fields': ['adoptionName', 'firstName'],
                    },
                },
            ],
        },
    }
    result_api = Individual.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'individuals', search)
    result_rest = response.json
    assert len(result_api) == 0
    assert len(result_api) == len(result_rest)

    # Search individuals (matching first name)
    searchTerm = 'Zebra'
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {'term': {'guid': searchTerm}},
                {
                    'query_string': {
                        'query': '*{}*'.format(searchTerm),
                        'fields': ['adoptionName', 'firstName'],
                    },
                },
            ],
        },
    }
    result_api = Individual.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'individuals', search)
    result_rest = response.json
    assert len(result_api) == 1
    assert len(result_api) == len(result_rest)
    assert str(result_api[0]) == result_rest[0].get('guid')

    # Search individuals (matching first name only)
    searchTerm = 'Zebra'
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {
                    'query_string': {
                        'query': '*{}*'.format(searchTerm),
                        'fields': ['adoptionName', 'firstName'],
                    },
                },
            ],
        },
    }
    result_api = Individual.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'individuals', search)
    result_rest = response.json
    assert len(result_api) == 1
    assert len(result_api) == len(result_rest)
    assert str(result_api[0]) == result_rest[0].get('guid')

    # Search individuals (matching GUID first)
    searchTerm = individual_1_id
    search = {
        'bool': {
            'minimum_should_match': 1,
            'should': [
                {
                    'term': {
                        'guid': searchTerm,
                    }
                },
            ],
        },
    }
    result_api = Individual.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'individuals', search)
    result_rest = response.json
    assert len(result_api) == 1
    assert len(result_api) == len(result_rest)
    assert str(result_api[0]) == result_rest[0].get('guid')
