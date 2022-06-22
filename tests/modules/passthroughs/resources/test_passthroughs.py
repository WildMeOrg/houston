# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.utils as test_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('passthroughs'), reason='Site-settings module disabled'
)
def _read_passthrough(
    flask_app_client,
    user,
    path,
    expected_status_code=200,
):
    res = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='passthroughs:read',
        path=path,
        expected_status_code=expected_status_code,
        response_200=None,
        response_error={'message'},
    )
    return res


@pytest.mark.skipif(
    module_unavailable('passthroughs'), reason='Passthroughs module disabled'
)
def test_read_sage_jobs_passthrough(flask_app_client, researcher_1):
    _read_passthrough(flask_app_client, researcher_1, '/api/v1/passthroughs/sage/jobs')
