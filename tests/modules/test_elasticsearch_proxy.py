# -*- coding: utf-8 -*-
"""\
This tests the search endpoint's proxy abilities

For testing the aspects of the data in elasticsearch,
see the _gumby_ library.

"""
import gumby
import pytest

from app.extensions import is_extension_enabled
from tests.utils import extension_unavailable


# override gumby fixture definition
@pytest.fixture
def gumby_client(flask_app):
    if is_extension_enabled('elasticsearch'):
        return flask_app.elasticsearch
    else:
        from gumby import Client

        return Client(None)


@pytest.fixture
# original: def individuals(request, flask_app):
def individuals(gumby_faux_index_data):
    return gumby_faux_index_data[gumby.Individual]


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
class TestIndividualsSearchIndex:
    @pytest.fixture(autouse=True)
    def set_up(self, gumby_individual_index_name):
        self.target_url = f'/api/v1/search/proxy/{gumby_individual_index_name}'

    def test_no_criteria(self, flask_app_client, individuals):

        # Search without criteria
        resp = flask_app_client.post(self.target_url)

        # Check for search results
        data = resp.json
        assert data['hits']['total']['value'] == 10

    def test_with_body(self, flask_app_client, individuals):
        query = '{"query": {"match_all": {}}}'

        # Search without criteria
        resp = flask_app_client.post(self.target_url, data=query)

        # Check for search results
        data = resp.get_json()
        assert data['hits']['total']['value'] == 10
