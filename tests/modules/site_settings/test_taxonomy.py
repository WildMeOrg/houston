# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring

from tests.modules.site_settings.resources import utils as setting_utils
from app.modules.site_settings.models import Taxonomy
import pytest

from tests.utils import (
    extension_unavailable,
)


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_taxonomy(flask_app_client, admin_user):
    setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    with pytest.raises(ValueError):
        tx = Taxonomy('fubarxxx')
    with pytest.raises(ValueError):
        tx = Taxonomy(99999999999999)
    tx = Taxonomy(624996)
    assert tx.scientificName == 'Equus quagga'
    assert tx.commonNames == ['plains zebra']
    tx = Taxonomy('Equus quagga')
    assert tx.itisTsn == 624996
    assert tx.commonNames == ['plains zebra']
    tx = Taxonomy.find_fuzzy('equs qaaga')
    assert tx
    assert tx.scientificName == 'Equus quagga'
    tx = Taxonomy.find_fuzzy_list(['cow', 'zebraa', 'cat'])
    assert len(tx) == 1
    assert tx[0].scientificName == 'Equus quagga'
