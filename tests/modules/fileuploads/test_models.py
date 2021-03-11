# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import config
import os
from app.modules.fileuploads.models import FileUpload


def _source_file():
    return os.path.join(
        config.TestingConfig.PROJECT_ROOT,
        'tests',
        'submissions',
        'test-000',
        'zebra.jpg',
    )


def test_fileupload_create_delete(db):

    source_file = _source_file()
    sz = os.path.getsize(source_file)
    assert sz > 0

    fup = FileUpload.create_fileupload_from_path(source_file, copy=True)
    with db.session.begin():
        db.session.add(fup)
    fup_guid = fup.guid

    fup_path = fup.get_absolute_path()
    fup_sz = os.path.getsize(fup_path)
    assert sz == fup_sz
    f_test = FileUpload.query.get(fup_guid)
    assert f_test is not None

    fup.delete()

    # now verify its all gone
    f_test = FileUpload.query.get(fup_guid)
    assert f_test is None
    assert not os.path.exists(fup_path)


def test_fileuploads_get_src(flask_app_client, db):
    source_file = _source_file()
    sz = os.path.getsize(source_file)
    fup = FileUpload.create_fileupload_from_path(source_file, copy=True)
    with db.session.begin():
        db.session.add(fup)
    response = flask_app_client.get('/api/v1/fileuploads/src/' + str(fup.guid))
    response.close()  # h/t https://github.com/pallets/flask/issues/2468#issuecomment-517797518
    fup.delete()
    assert response.status_code == 200
    assert response.content_type == 'image/jpeg'
    assert response.content_length == sz
