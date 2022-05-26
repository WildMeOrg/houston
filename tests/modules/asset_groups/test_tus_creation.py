# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import os
import pathlib
import shutil

import pytest

from tests.extensions.tus import utils as tus_utils
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_from_tus(flask_app, db, researcher_1, test_root):
    from app.modules.asset_groups.models import AssetGroup
    from app.utils import HoustonException

    tid = tus_utils.get_transaction_id()  # '11111111-1111-1111-1111-111111111111'

    # first no such dir exists
    transaction_dir = pathlib.Path(
        tus_utils.tus_upload_dir(flask_app, transaction_id=tid)
    )
    if (transaction_dir).exists():
        shutil.rmtree(transaction_dir)
    with pytest.raises(OSError):
        sub, _ = AssetGroup.create_from_tus('PYTEST', researcher_1, tid)

    # now with a file dir+files but ask for wrong one
    tid, valid_file = tus_utils.prep_tus_dir(test_root)
    with pytest.raises(HoustonException):
        sub, _ = AssetGroup.create_from_tus(
            'PYTEST', researcher_1, tid, paths=['fail.jpg']
        )

    # test with explicit paths (should succeed)
    tid, valid_file = tus_utils.prep_tus_dir(test_root)
    sub, _ = AssetGroup.create_from_tus(
        'PYTEST', researcher_1, tid, paths=[valid_file], foreground=True
    )
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()

    # test with no paths (should succeed same as above)
    tid, valid_file = tus_utils.prep_tus_dir(test_root)
    sub, _ = AssetGroup.create_from_tus('PYTEST', researcher_1, tid, foreground=True)
    assert len(sub.assets) == 1
    assert sub.assets[0].path == valid_file
    if os.path.exists(sub.get_absolute_path()):
        shutil.rmtree(sub.get_absolute_path())
    sub.delete()
