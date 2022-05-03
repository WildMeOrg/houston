# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import pytest
import uuid

from tests import utils

# from app.modules.site_settings.models import SiteSetting


# technically this has nothing to do with IntelligentAgent but these utils just came in via this work
#  and i am not really sure where to put tests for utils.py ??
def test_peristent_value(flask_app):
    from app.utils import get_redis_connection, set_persisted_value, get_persisted_value

    if utils.redis_unavailable():
        pytest.skip('redis unavailable')

    conn = get_redis_connection()
    assert conn

    key = 'fubar_test'
    val = str(uuid.uuid4())
    set_persisted_value(key, val)
    assert get_persisted_value(key) == val
