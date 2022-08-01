# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

import pytest

from app.modules.site_settings.models import Taxonomy
from tests.modules.site_settings.resources import utils as setting_utils


def test_taxonomy(flask_app_client, admin_user):
    conf_tx = setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    with pytest.raises(ValueError):
        tx = Taxonomy('fubarxxx')
    with pytest.raises(ValueError):
        tx = Taxonomy(99999999999999)
    if conf_tx.get('itisTsn'):
        tx = Taxonomy(conf_tx['itisTsn'])
        assert tx.scientificName == conf_tx['scientificName']
        assert tx.commonNames == conf_tx.get('commonNames')
    tx = Taxonomy(conf_tx['scientificName'])
    assert tx.itisTsn == conf_tx.get('itisTsn')
    assert tx.commonNames == conf_tx.get('commonNames')
    tx = Taxonomy.find_fuzzy(conf_tx['scientificName'] + 'es')
    assert tx
    assert tx.scientificName == conf_tx['scientificName']
    tx = Taxonomy.find_fuzzy_list(['cow', 'a' + conf_tx['scientificName'], 'cat'])
    assert len(tx) == 1
    assert tx[0].scientificName == conf_tx['scientificName']
