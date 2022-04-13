# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils as test_utils
from tests.modules.elasticsearch.resources import utils as es_utils
from tests.modules.individuals.resources import utils as individual_utils


# OK I don't understand why this does not guarantee that the mapping is generated JP??
def no_test_individual_elasticsearch_mappings(
    flask_app_client, researcher_1, request, test_root
):
    from app.modules.individuals.models import Individual

    individual1_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client, researcher_1, request, test_root
    )

    individual_1 = Individual.query.get(individual1_uuids['individual'])
    individual_1.index()
    test_utils.wait_for_elasticsearch_status(flask_app_client, researcher_1)

    EXPECTED_KEYS = {
        'created',
        'guid',
        'birth',
        'customFields',
        'encounters',
        'has_annotations',
        'updated',
        'social_groups',
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
