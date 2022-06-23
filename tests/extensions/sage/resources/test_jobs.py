# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.utils as test_utils
from tests.utils import extension_unavailable


def _read_sage(
    flask_app_client,
    user,
    path,
    expected_status_code=200,
):
    res = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='sage:read',
        path=path,
        expected_status_code=expected_status_code,
        response_200=None,
        response_error={'message'},
    )
    return res


@pytest.mark.skipif(extension_unavailable('sage'), reason='Sage extension disabled')
def test_read_sage_jobs_passthrough(flask_app_client, researcher_1):
    _read_sage(flask_app_client, researcher_1, '/api/v1/sage/jobs')
