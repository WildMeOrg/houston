# -*- coding: utf-8 -*-
"""\
This tests the search endpoint's proxy abilities

For testing the aspects of the data in elasticsearch,
see the _gumby_ library.

"""
import gumby
import pytest


# override gumby fixture definition
@pytest.fixture
def gumby_client(flask_app):
    return flask_app.elasticsearch


@pytest.fixture
# original: def individuals(request, flask_app):
def individuals(gumby_faux_index_data):
    return gumby_faux_index_data[gumby.Individual]


class TestIndividualsSearchIndex:
    @pytest.fixture(autouse=True)
    def set_up(self, gumby_individual_index_name):
        self.target_url = f'/api/v1/search/{gumby_individual_index_name}'

    def test_no_criteria(self, flask_app_client, individuals):

        # Search without criteria
        resp = flask_app_client.post(self.target_url)

        # Check for search results
        data = resp.get_json()
        assert data['hits']['total']['value'] == 10

    def test_with_body(self, flask_app_client, individuals):
        query = '{"query": {"match_all": {}}}'

        # Search without criteria
        resp = flask_app_client.post(self.target_url, data=query)

        # Check for search results
        data = resp.get_json()
        assert data['hits']['total']['value'] == 10
