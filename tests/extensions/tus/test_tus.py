# -*- coding: utf-8 -*-
import pathlib
import time
import uuid
from unittest import mock

from app.extensions import tus

from . import utils


def test_tus_cleanup(flask_app, test_root, request):
    log_patcher = mock.patch('app.extensions.tus.log')
    log = log_patcher.start()
    request.addfinalizer(log_patcher.stop)

    ttl_seconds = flask_app.config['UPLOADS_TTL_SECONDS']

    # Create some files in tus dir
    tid = str(uuid.uuid4())
    utils.prep_tus_dir(test_root, transaction_id=tid)
    request.addfinalizer(lambda: utils.cleanup_tus_dir(tid))
    tus_dir = tus.tus_upload_dir(flask_app, transaction_id=tid)

    # Try tus_cleanup (should not clean up anything)
    tus.tus_cleanup()
    assert log.info.call_args_list[0] == mock.call(
        f'Using clean-up TTL seconds (config UPLOADS_TTL_SECONDS) of {ttl_seconds}'
    )
    assert log.info.call_args_list[1] == mock.call(
        f'Skipping Tus pending file (Age: a moment, Remaining: a day): {repr(tus_dir)}'
    )
    assert pathlib.Path(tus_dir).exists()
    log.reset_mock()

    # Mock time to add 80 minutes to the current time and
    # tus_cleanup should not delete the directory
    current_time = time.time()
    with mock.patch('time.time') as mock_time:
        mock_time.return_value = current_time + 80 * 60
        tus.tus_cleanup()
    assert log.info.call_args_list == [
        mock.call(
            f'Using clean-up TTL seconds (config UPLOADS_TTL_SECONDS) of {ttl_seconds}'
        ),
        mock.call(
            f'Skipping Tus pending file (Age: an hour, Remaining: 22 hours): {repr(tus_dir)}'
        ),
    ]
    assert pathlib.Path(tus_dir).exists()
    log.reset_mock()

    # Mock time to add 30 hours to the current time and
    # tus_cleanup should delete the directory
    with mock.patch('time.time') as mock_time:
        mock_time.return_value = current_time + 30 * 60 * 60
        tus.tus_cleanup()
    assert log.info.call_args_list == [
        mock.call(
            f'Using clean-up TTL seconds (config UPLOADS_TTL_SECONDS) of {ttl_seconds}'
        ),
        mock.call(f'Deleting too old (21599 seconds) Tus pending file: {repr(tus_dir)}'),
    ]
    assert not pathlib.Path(tus_dir).exists()
