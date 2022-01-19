# -*- coding: utf-8 -*-
""" Client initialization for Elasticsearch """
from gumby import Client, initialize_indexes_by_model

from app.extensions import is_extension_enabled

if not is_extension_enabled('elasticsearch'):
    raise RuntimeError('Elastic Search is not enabled')


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.elasticsearch = Client(app.config['ELASTICSEARCH_HOSTS'])

    # Initialize indexes if they don't already exists
    initialize_indexes_by_model(using=app.elasticsearch)
