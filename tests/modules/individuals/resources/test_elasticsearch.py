# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils as test_utils
from tests.modules.elasticsearch.resources import utils as es_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.utils import module_unavailable

import pytest


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    test_utils.extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension disabled',
)
def test_individual_elasticsearch_mappings(
    flask_app_client, researcher_1, request, test_root
):
    from app.modules.individuals.models import Individual
    from app.extensions import elasticsearch as es

    individual1_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client, researcher_1, request, test_root
    )

    individual_1 = Individual.query.get(individual1_uuids['individual'])

    es.es_delete_index(individual_1._index())
    with es.session.begin(blocking=True, forced=True):
        individual_1.index()

    EXPECTED_KEYS = {
        'created',
        'guid',
        'birth',
        'customFields',
        'encounters',
        'has_annotations',
        'updated',
        # 'social_groups',
        'indexed',
        'names',
        'last_seen',
        'death',
        'comments',
        '_schema',
    }

    # Get the response and just validate that it has the correct keys
    test_utils.get_dict_via_flask(
        flask_app_client,
        researcher_1,
        scopes='search:read',
        path=es_utils.get_mapping_path('individual'),
        expected_status_code=200,
        response_200=EXPECTED_KEYS,
    )
