# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils as test_utils
from tests.modules.elasticsearch.resources import utils as es_utils


# Likewise, this should work but no sighting has been indexed properly so cannot run this test
def no_test_sighting_elasticsearch_mappings(flask_app_client, researcher_1):
    EXPECTED_KEYS = {
        'created',
        'guid',
        'updated',
        'indexed',
        'comments',
        'time',
        'timeSpecificity',
        'location',
        'owners',
        'taxonomy_guid',
        'customFields',
    }

    # Get the response and just validate that it has the correct keys
    test_utils.get_dict_via_flask(
        flask_app_client,
        researcher_1,
        scopes='search:read',
        path=es_utils.get_mapping_path('sighting'),
        expected_status_code=200,
        response_200=EXPECTED_KEYS,
    )
