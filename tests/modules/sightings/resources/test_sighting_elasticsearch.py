# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

from tests import utils as test_utils
from tests.extensions.elasticsearch.resources import utils as es_utils
from tests.modules.sightings.resources import utils


EXPECTED_KEYS = {
    'created',
    'guid',
    'updated',
    'indexed',
    'comments',
    'time',
    'timeSpecificity',
    'locationId_id',
    'locationId_value',
    'owners',
    'taxonomy_guid',
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

    sighting_guid = utils.create_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
    )['sighting']
    # Force created sighting to be indexed in elasticsearch
    Sighting.query.get(sighting_guid).index()

    test_utils.get_list_via_flask(
        flask_app_client,
        researcher_1,
        scopes='sightings:read',
        path='/api/v1/sightings/search',
        expected_status_code=200,
        expected_fields=EXPECTED_KEYS,
    )
