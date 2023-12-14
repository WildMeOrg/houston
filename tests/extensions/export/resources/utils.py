# -*- coding: utf-8 -*-
"""
integrity resources utils
-------------
"""
from tests import utils as test_utils


def export_search(
    flask_app_client,
    user,
    data,
    class_name='sightings',
    expected_status_code=200,
    expected_error='',
    request=None,
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        user,
        f'{class_name}:read',
        f'/api/v1/{class_name}/export',
        data,
        expected_status_code,
        None,
        expected_error=expected_error,
    )
    return resp


def clear_files():
    import glob
    import os

    for f in glob.glob('/tmp/export/*/codex-export-Unknown-*.xls'):
        os.remove(f)
