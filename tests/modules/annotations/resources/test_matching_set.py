# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import pytest

from tests import utils
from tests.modules.annotations.resources import utils as annot_utils
from tests.modules.encounters.resources import utils as enc_utils
from tests.modules.site_settings.resources import utils as setting_utils
from tests.utils import (
    elasticsearch,
    extension_unavailable,
    module_unavailable,
    wait_for_elasticsearch_status,
)


@pytest.mark.skipif(
    module_unavailable('asset_groups'),
    reason='AssetGroups module disabled',
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension disabled',
)
def test_annotation_matching_set(
    flask_app_client,
    researcher_1,
    admin_user,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.extensions import elasticsearch as es
    from app.modules.annotations.models import Annotation

    if es.is_disabled():
        pytest.skip('Elasticsearch disabled (via command-line)')

    # make sure we dont have stray annots around
    Annotation.query.delete()

    enc1_uuids = enc_utils.create_encounter(
        flask_app_client, researcher_1, request, test_root
    )
    enc1_guid = enc1_uuids['encounters'][0]
    enc1_asset_guid = enc1_uuids['assets'][0]
    enc1_uuids = enc_utils.create_encounter(
        flask_app_client, researcher_1, request, test_root
    )
    enc1_guid = enc1_uuids['encounters'][0]
    enc1_asset_guid = enc1_uuids['assets'][0]

    tx = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    assert tx
    assert 'id' in tx
    taxonomy_guid = tx['id']
    locationId = 'erehwon'
    patch_data = [
        utils.patch_replace_op('taxonomy', taxonomy_guid),
        utils.patch_replace_op('locationId', locationId),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        enc1_guid,
        researcher_1,
        patch_data,
    )

    viewpoint = 'upfront'
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        enc1_asset_guid,
        enc1_guid,
        viewpoint=viewpoint,
    )

    annotation_guid = response.json['guid']
    annotation = Annotation.query.get(annotation_guid)
    assert annotation.asset_guid == uuid.UUID(enc1_asset_guid)

    request.addfinalizer(annotation.delete)
    # must have this for matching
    annotation.content_guid = uuid.uuid4()

    # now we need a few other annots to see how they fair in matching_set creation
    enc2_uuids = enc_utils.create_encounter(
        flask_app_client, researcher_1, request, test_root
    )
    enc2_guid = enc2_uuids['encounters'][0]
    enc2_asset_guid = enc2_uuids['assets'][0]
    patch_data = [
        utils.patch_replace_op('taxonomy', taxonomy_guid),
        utils.patch_replace_op('locationId', locationId),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        enc2_guid,
        researcher_1,
        patch_data,
    )
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        enc2_asset_guid,
        enc2_guid,  # same enc as target, so should be skipped
        viewpoint='frontright',
    )
    annot0 = Annotation.query.get(response.json['guid'])
    request.addfinalizer(annot0.delete)
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        enc2_asset_guid,
        enc2_guid,
        viewpoint='back',  # not neighbor
    )
    annot1 = Annotation.query.get(response.json['guid'])
    request.addfinalizer(annot1.delete)
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        enc2_asset_guid,
        enc2_guid,
        viewpoint='frontright',
    )
    # this one should match
    annotation_match_guid = response.json['guid']
    annotation_match = Annotation.query.get(annotation_match_guid)
    request.addfinalizer(annotation_match.delete)
    annotation_match.content_guid = uuid.uuid4()

    # first lets query *all* annots
    wait_for_elasticsearch_status(flask_app_client, researcher_1)
    annots = Annotation.elasticsearch({})
    assert len(annots) == 4

    query = annotation.get_matching_set_default_query()
    assert 'bool' in query
    assert 'filter' in query['bool']
    # omg this is tedious so just cutting to the chase (9 viewpoint/neighbors)
    assert len(query['bool']['filter'][0]['bool']['should']) == 9
    assert query['bool']['must_not']['match']['encounter_guid'] == str(enc1_guid)

    # will just use default (as above)
    matching_set = annotation.get_matching_set()
    assert len(matching_set) >= 1
    assert annotation_match_guid in [str(val.guid) for val in matching_set]

    # test resolving of non-default queries
    try:
        annotation.resolve_matching_set_query('fail')
    except ValueError as ve:
        assert str(ve) == 'must be passed a dict ES query'

    # unknown/atypical/untouched
    query_in = {'foo': 'bar'}
    resolved = annotation.resolve_matching_set_query(query_in)
    assert resolved == query_in

    # test hook that indexes annotation when encounter is indexed
    was_indexed = annotation.indexed
    annotation.encounter.index()
    assert annotation.indexed > was_indexed
    # test same for sighting
    was_indexed = annotation.indexed
    annotation.encounter.sighting.index()
    assert annotation.indexed > was_indexed

    annotation.encounter_guid = None
    try:
        annotation.resolve_matching_set_query(query_in)
    except ValueError as ve:
        assert str(ve) == 'cannot resolve query on Annotation with no Encounter'


# note: despite the name of this test, it can run without elasticsearch enabled,
#   as it only is testing the schema content/construction
@pytest.mark.skipif(
    module_unavailable('asset_groups'),
    reason='AssetGroups module disabled',
)
def test_annotation_elasticsearch(
    flask_app_client,
    researcher_1,
    admin_user,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation
    from app.modules.annotations.schemas import AnnotationElasticsearchSchema

    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    enc_guid = uuids['encounters'][0]
    asset_guid = uuids['assets'][0]

    tx = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    assert tx
    assert 'id' in tx
    taxonomy_guid = tx['id']
    locationId = 'erehwon'
    patch_data = [
        utils.patch_replace_op('taxonomy', taxonomy_guid),
        utils.patch_replace_op('locationId', locationId),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        enc_guid,
        researcher_1,
        patch_data,
    )

    viewpoint = 'upfront'
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        asset_guid,
        enc_guid,
        viewpoint=viewpoint,
    )

    annotation_guid = response.json['guid']
    annotation = Annotation.query.get(annotation_guid)
    request.addfinalizer(annotation.delete)
    annotation.content_guid = uuid.uuid4()

    # make sure the schema contains what we need
    schema = AnnotationElasticsearchSchema()
    sdump = schema.dump(annotation)
    assert sdump
    assert sdump.data
    assert sdump.data.get('owner_guid') == str(researcher_1.guid)
    assert sdump.data.get('asset_guid') == asset_guid
    assert sdump.data.get('content_guid') == str(annotation.content_guid)
    assert sdump.data.get('taxonomy_guid') == taxonomy_guid
    assert sdump.data.get('locationId') == locationId
    assert sdump.data.get('guid') == str(annotation.guid)
    assert sdump.data.get('bounds') == {'rect': [0, 1, 2, 3], 'theta': 0}
    assert sdump.data.get('viewpoint') == viewpoint
    assert sdump.data.get('encounter_guid') == enc_guid
    assert sdump.data.get('sighting_guid') == uuids['sighting']


@pytest.mark.skipif(
    module_unavailable('asset_groups'),
    reason='AssetGroups module disabled',
)
def test_annotation_matching_set_macros(
    flask_app_client,
    researcher_1,
    admin_user,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation

    # make sure we dont have stray annots around
    Annotation.query.delete()

    enc1_uuids = enc_utils.create_encounter(
        flask_app_client, researcher_1, request, test_root
    )
    enc1_guid = enc1_uuids['encounters'][0]
    enc1_asset_guid = enc1_uuids['assets'][0]
    enc1_uuids = enc_utils.create_encounter(
        flask_app_client, researcher_1, request, test_root
    )
    enc1_guid = enc1_uuids['encounters'][0]
    enc1_asset_guid = enc1_uuids['assets'][0]
    sighting_guid = enc1_uuids['sighting']

    tx = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    assert tx
    assert 'id' in tx
    taxonomy_guid = tx['id']
    locationId = 'erehwon'
    patch_data = [
        utils.patch_replace_op('taxonomy', taxonomy_guid),
        utils.patch_replace_op('locationId', locationId),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        enc1_guid,
        researcher_1,
        patch_data,
    )

    viewpoint = 'upfront'
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        enc1_asset_guid,
        enc1_guid,
        viewpoint=viewpoint,
    )

    annotation_guid = response.json['guid']
    annotation = Annotation.query.get(annotation_guid)
    assert annotation.asset_guid == uuid.UUID(enc1_asset_guid)

    request.addfinalizer(annotation.delete)

    # this is a kind of bunk query (in terms of useful for ES), but good enough for testing
    query = {
        'filter': {
            'A': '_MACRO_annotation_sighting_guid',
            'B': [
                {'bool': '_MACRO_annotation_encounter_guid'},
            ],
            'C': {
                'match': '_MACRO_annotation_neighboring_viewpoints_clause',
            },
        }
    }
    replaced = annotation.matching_set_query_replace_macros(query)
    assert replaced['filter']['A'] == sighting_guid
    assert len(replaced['filter']['B']) == 1
    assert replaced['filter']['B'][0]['bool'] == enc1_guid
    assert 'match' in replaced['filter']['C']
    vps = annotation.get_neighboring_viewpoints()
    assert len(replaced['filter']['C']['match']['should']) == len(vps)
    for vp in vps:
        assert {'term': {'viewpoint': vp}} in replaced['filter']['C']['match']['should']


@pytest.mark.skipif(
    module_unavailable('asset_groups'),
    reason='AssetGroups module disabled',
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension or module disabled',
)
def test_search_with_elasticsearch(
    flask_app_client,
    researcher_1,
    admin_user,
    request,
    test_root,
):
    # pylint: disable=invalid-name
    from app.extensions import elasticsearch as es
    from app.modules.annotations.models import Annotation

    uuids = enc_utils.create_encounter(flask_app_client, researcher_1, request, test_root)
    enc_guid = uuids['encounters'][0]
    asset_guid = uuids['assets'][0]

    tx = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    assert tx
    assert 'id' in tx
    taxonomy_guid = tx['id']
    locationId = 'erehwon'
    patch_data = [
        utils.patch_replace_op('taxonomy', taxonomy_guid),
        utils.patch_replace_op('locationId', locationId),
    ]
    enc_utils.patch_encounter(
        flask_app_client,
        enc_guid,
        researcher_1,
        patch_data,
    )

    viewpoint = 'upfront'
    response = annot_utils.create_annotation(
        flask_app_client,
        researcher_1,
        asset_guid,
        enc_guid,
        viewpoint=viewpoint,
    )

    annotation_guid = response.json['guid']
    annotation = Annotation.query.get(annotation_guid)
    request.addfinalizer(annotation.delete)
    annotation.content_guid = uuid.uuid4()

    # Index all users
    with es.session.begin(blocking=True):
        Annotation.index_all(force=True)

    # Wait for elasticsearch to catch up
    wait_for_elasticsearch_status(flask_app_client, researcher_1)
    assert len(Annotation.elasticsearch(None, load=False)) == 1

    locationId = annotation.get_location_id()
    search = {
        'bool': {
            'filter': [
                {
                    'bool': {
                        'minimum_should_match': 1,
                        'should': [
                            {
                                'term': {
                                    'locationId': locationId,
                                }
                            },
                        ],
                    }
                },
                {
                    'bool': {
                        'minimum_should_match': 1,
                        'should': [
                            {'term': {'viewpoint': 'up'}},
                            {'term': {'viewpoint': 'upleft'}},
                            {'term': {'viewpoint': 'upfrontleft'}},
                            {'term': {'viewpoint': 'upfront'}},
                            {'term': {'viewpoint': 'upfrontright'}},
                            {'term': {'viewpoint': 'upright'}},
                            {'term': {'viewpoint': 'upbackright'}},
                            {'term': {'viewpoint': 'upback'}},
                            {'term': {'viewpoint': 'upbackleft'}},
                        ],
                    }
                },
                {'exists': {'field': 'encounter_guid'}},
            ],
            'must_not': {'match': {'encounter_guid': 'does not exist'}},
        }
    }
    result_api = Annotation.elasticsearch(search, load=False)
    response = elasticsearch(flask_app_client, researcher_1, 'annotations', search)
    result_rest = response.json
    assert len(result_api) == 1
    assert len(result_api) == len(result_rest)
    assert str(result_api[0]) == result_rest[0].get('guid')
