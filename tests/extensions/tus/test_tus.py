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

    # Create some files in tus dir
    tid = str(uuid.uuid4())
    utils.prep_tus_dir(test_root, transaction_id=tid)
    request.addfinalizer(lambda: utils.cleanup_tus_dir(tid))
    tus_dir = tus.tus_upload_dir(flask_app, transaction_id=tid)

    # Try tus_cleanup (should not clean up anything)
    tus.tus_cleanup()
    assert log.info.call_args_list[0] == mock.call(
        'Using clean-up TTL seconds (config UPLOADS_TTL_SECONDS) of 3600'
    )
    assert log.info.call_args_list[1] in [
        mock.call(
            f'Skipping Tus pending file (Age: a moment, Remaining: an hour): {repr(tus_dir)}'
        ),
        mock.call(
            f'Skipping Tus pending file (Age: a moment, Remaining: 59 minutes): {repr(tus_dir)}'
        ),
    ]
    assert pathlib.Path(tus_dir).exists()
    log.reset_mock()

    # Mock time to add 4000 seconds to the current time and
    # tus_cleanup should delete the directory
    current_time = time.time()
    with mock.patch('time.time') as mock_time:
        mock_time.return_value = current_time + 4000
        tus.tus_cleanup()
    assert log.info.call_args_list == [
        mock.call('Using clean-up TTL seconds (config UPLOADS_TTL_SECONDS) of 3600'),
        mock.call(f'Deleting too old (399 seconds) Tus pending file: {repr(tus_dir)}'),
    ]
    assert not pathlib.Path(tus_dir).exists()
