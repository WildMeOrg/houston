# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import logging

import pytest

from tests import utils as test_utils
from tests.utils import module_unavailable

log = logging.getLogger(__name__)


@pytest.mark.skipif(
    module_unavailable('individuals'), reason='Individuals module disabled'
)
def test_clear_up_empty_individuals(flask_app_client, researcher_1, admin_user):
    # shouldn't be allowed
    test_utils.post_via_flask(
        flask_app_client,
        researcher_1,
        scopes='individuals:write',
        path='/api/v1/individuals/remove_all_empty',
        data={},
        expected_status_code=403,
        response_200={},
    )
    # should be allowed
    resp = test_utils.post_via_flask(
        flask_app_client,
        admin_user,
        scopes='individuals:write',
        path='/api/v1/individuals/remove_all_empty',
        data={},
        expected_status_code=None,
        response_200={},
    )
    assert resp.status_code == 200
