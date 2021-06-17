# -*- coding: utf-8 -*-
"""\
This tests the search endpoints representation and parameter usage.

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
# def individuals(request, flask_app):
def individuals(gumby_faux_index_data):
    return gumby_faux_index_data[gumby.Individual]


class TestIndividualsSearch:
    target_url = '/api/v1/search/individuals'

    def test_no_criteria(self, flask_app_client, individuals):
        client = flask_app_client

        # Search without criteria
        resp = client.post(self.target_url)

        # Check for search results
        data = resp.get_json()
        assert data['hits']['total']['value'] == 10

    def test_broad_search(self, flask_app_client, individuals):
        search_criteria = {
            'sex': 'unknown',
            # 'status': 'animate',
            # 'has_annotation': True,
        }

        client = flask_app_client

        # Search without criteria
        resp = client.post(self.target_url, data=search_criteria)

        # Check for search results
        data = resp.get_json()
        assert data['hits']['total']['value'] == 5

    def test_name_search(self, flask_app_client, individuals):
        search_criteria = {
            'name': 'TI-68435',
        }

        client = flask_app_client

        # Search without criteria
        resp = client.post(self.target_url, data=search_criteria)

        # Check for search results
        data = resp.get_json()
        assert data['hits']['total']['value'] == 1
