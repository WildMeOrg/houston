# -*- coding: utf-8 -*-
""" Client initialization for Elasticsearch """
from gumby import Client


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.elasticsearch = Client(app.config['ELASTICSEARCH_HOSTS'])
