# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import os
import pytest
import shutil


def test_create_submission_from_tus(db, researcher_1):

    from app.modules.asset_groups.models import Submission
    from tests.modules.sightings.resources.utils import (
        prep_tus_dir,
        get_transaction_id,
    )  # recycle

    tid = get_transaction_id()  # '11111111-1111-1111-1111-111111111111'

    # first no such dir exists
    with pytest.raises(OSError):
        sub = Submission.create_submission_from_tus('PYTEST', researcher_1, tid)

    # now with a file dir+files but ask for wrong one
    tid, valid_file = prep_tus_dir()
    with pytest.raises(AssertionError):
        sub = Submission.create_submission_from_tus(
            'PYTEST', researcher_1, tid, paths={'fail.jpg'}
        )

    # test with explicit paths (should succeed)
    sub = Submission.create_submission_from_tus(
        'PYTEST', researcher_1, tid, paths={valid_file}
    )
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()

    # test with no paths (should succeed same as above)
    tid, valid_file = prep_tus_dir()
    sub = Submission.create_submission_from_tus('PYTEST', researcher_1, tid)
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()
