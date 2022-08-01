# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from app.extensions import elasticsearch as es
from tests import utils as test_utils
from tests.extensions.elasticsearch.resources import utils as es_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.utils import extension_unavailable, module_unavailable


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension disabled',
)
def test_individual_elasticsearch_mappings(
    flask_app_client, researcher_1, request, test_root
):
    from app.modules.individuals.models import Individual

    individual1_uuids = individual_utils.create_individual_and_sighting(
        flask_app_client, researcher_1, request, test_root
    )

    individual_1 = Individual.query.get(individual1_uuids['individual'])

    es.es_delete_index(individual_1._index())
    with es.session.begin(blocking=True, forced=True):
        individual_1.index()
    es.es_index_mappings_patch(Individual)

    EXPECTED_KEYS = {
        'created',
        'guid',
        'customFields',
        'encounters',
        'has_annotations',
        'updated',
        'indexed',
        'last_seen',
        'last_seen_specificity',
        'firstName_keyword',
        'num_encounters',
        '_schema',
        'birth',
        'death',
        'names',
        'firstName',
        'comments',
        # 'social_groups',
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


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension disabled',
)
def test_returned_schema(flask_app_client, researcher_1, admin_user, request, test_root):
    import datetime

    from app.modules.individuals.models import Individual
    from tests.modules.site_settings.resources import utils as setting_utils

    # make a taxonomy to use
    response = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    tx_guid = response['id']

    timestamp = datetime.datetime.now().isoformat() + '+00:00'
    sighting_data = {
        'encounters': [
            {
                'locationId': str(uuid.uuid4()),
                'taxonomy': tx_guid,
                'time': timestamp,
                'timeSpecificity': 'time',
            }
        ],
        'locationId': str(uuid.uuid4()),
        'time': timestamp,
        'timeSpecificity': 'time',
        'taxonomies': tx_guid,
    }

    # note that taxonomy is not set on the individual in this test (we are checking it will inherit from encounters)
    individual_data = {
        'sex': 'female',
        'names': [
            {'context': 'firstName', 'value': 'Z432'},
            {'context': 'Christian name', 'value': 'Zachariah'},
        ],
    }

    create_resp = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data=individual_data,
        sighting_data=sighting_data,
    )
    individual_guid = create_resp['individual']
    enc_guid = create_resp['encounters'][0]
    with es.session.begin(blocking=True, forced=True):
        Individual.query.get(individual_guid).index()

    search_resp = test_utils.elasticsearch(flask_app_client, researcher_1, 'individuals')
    es_indy = search_resp.json[0]

    assert es_indy['guid'] == individual_guid
    assert es_indy['sex'] == 'female'
    assert es_indy['names'] == ['Z432', 'Zachariah']
    assert es_indy['taxonomy_guid'] == tx_guid

    # check encounter is just a guid
    assert es_indy['encounters'] == [enc_guid]
    assert es_indy['num_encounters'] == 1
