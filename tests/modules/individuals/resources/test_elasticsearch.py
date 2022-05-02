# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests import utils as test_utils
from tests.modules.elasticsearch.resources import utils as es_utils
from tests.modules.individuals.resources import utils as individual_utils
from tests.utils import module_unavailable, extension_unavailable
from app.extensions import elasticsearch as es

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
        # 'names',
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


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch') or module_unavailable('elasticsearch'),
    reason='Elasticsearch extension or module disabled',
)
def test_elasticsearch_names(db, flask_app_client, researcher_1, request, test_root):
    from app.modules.individuals.models import Individual
    from app.modules.individuals.schemas import ElasticsearchIndividualSchema

    create_resp = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        individual_data={
            'names': [
                {'context': 'firstName', 'value': 'Z432'},
                {'context': 'Christian name', 'value': 'Zachariah'},
            ],
        },
    )
    ind = Individual.query.get(create_resp['individual'])
    with es.session.begin(blocking=True, forced=True):
        ind.index()
    body = {}
    indy = Individual.elasticsearch(body)[0]
    # actually load the ES schema
    es_schema = ElasticsearchIndividualSchema()
    es_indy = es_schema.dump(indy).data
    assert type(es_indy['names']) is list
    assert es_indy['names'] == ['Z432', 'Zachariah']


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch') or module_unavailable('elasticsearch'),
    reason='Elasticsearch extension or module disabled',
)
def test_elasticsearch_taxonomy(
    db, flask_app_client, admin_user, researcher_1, request, test_root
):
    from app.modules.individuals.models import Individual
    from app.modules.individuals.schemas import ElasticsearchIndividualSchema
    from tests.modules.site_settings.resources import utils as setting_utils
    import datetime

    # make a taxonomy to use
    response = setting_utils.read_main_settings(
        flask_app_client, admin_user, 'site.species'
    )
    assert 'value' in response.json['response']
    vals = response.json['response']['value']
    vals.append({'commonNames': ['Example'], 'scientificName': 'Exempli gratia'})
    response = setting_utils.modify_main_settings(
        flask_app_client,
        admin_user,
        {'_value': vals},
        'site.species',
    )
    response = setting_utils.read_main_settings(
        flask_app_client, admin_user, 'site.species'
    )
    assert 'response' in response.json and 'value' in response.json['response']
    tx_guid = response.json['response']['value'][-1]['id']

    timestamp = datetime.datetime.now().isoformat() + '+00:00'
    sighting_data = {
        'encounters': [
            {
                'locationId': 'enc-test',
                'taxonomy': tx_guid,
                'time': timestamp,
                'timeSpecificity': 'time',
            }
        ],
        'locationId': 'enc-test',
        'time': timestamp,
        'timeSpecificity': 'time',
        'taxonomies': tx_guid,
    }

    uuids = individual_utils.create_individual_and_sighting(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        sighting_data=sighting_data,
    )
    individual_id = uuids['individual']

    ind = Individual.query.get(individual_id)
    with es.session.begin(blocking=True, forced=True):
        ind.index()
    body = {}
    indy = Individual.elasticsearch(body)[0]
    # actually load the ES schema
    es_schema = ElasticsearchIndividualSchema()
    es_indy = es_schema.dump(indy).data

    assert es_indy['taxonomy_guid'] == tx_guid
