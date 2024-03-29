# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring

import os
import pathlib
import shutil
import uuid

import pytest
from PIL import Image

from app.modules.fileuploads.models import FileUpload, modify_image
from tests.utils import (
    TemporaryDirectoryUUID,
    copy_uploaded_file,
    create_transaction_dir,
    write_uploaded_file,
)


def cleanup_fileuploads_directory(fileuploads_directory):
    """Recursively clean up empty directories in fileuploads directory"""
    for c in fileuploads_directory.glob('*'):
        child = pathlib.Path(c)
        if child.is_dir():
            cleanup_fileuploads_directory(c)
            if not list(child.glob('*')):
                c.rmdir()


def test_fileupload_create_delete(db, flask_app, test_root, request):
    fup_dir = None
    FILEUPLOAD_BASE_PATH = pathlib.Path(flask_app.config.get('FILEUPLOAD_BASE_PATH'))

    def cleanup():
        if fup_dir and fup_dir.exists():
            shutil.rmtree(fup_dir)
        cleanup_fileuploads_directory(FILEUPLOAD_BASE_PATH)

    request.addfinalizer(cleanup)

    source_file = os.path.join(test_root, 'zebra.jpg')
    sz = os.path.getsize(source_file)
    assert sz > 0

    fup = FileUpload.create_fileupload_from_path(source_file, copy=True)
    with db.session.begin():
        db.session.add(fup)
    fup_guid = fup.guid

    fup_path = fup.get_absolute_path()
    fup_dir = pathlib.Path(fup_path)
    fup_sz = os.path.getsize(fup_path)
    assert sz == fup_sz
    f_test = FileUpload.query.get(fup_guid)
    assert f_test is not None

    fup.delete()

    # now verify its all gone
    f_test = FileUpload.query.get(fup_guid)
    assert f_test is None
    assert not os.path.exists(fup_path)


def test_fileupload_from_tus(db, flask_app, test_root, request):
    FILEUPLOAD_BASE_PATH = pathlib.Path(flask_app.config.get('FILEUPLOAD_BASE_PATH'))
    TRANSACTION_ID = str(uuid.uuid4())
    fup_dir = None

    def cleanup():
        if fup_dir and fup_dir.exists():
            shutil.rmtree(fup_dir)
        cleanup_fileuploads_directory(FILEUPLOAD_BASE_PATH)

    request.addfinalizer(cleanup)
    tus_dir = create_transaction_dir(flask_app, TRANSACTION_ID)
    copy_uploaded_file(test_root, 'zebra.jpg', tus_dir, 'a.jpg')

    # Create fileupload using file from tus
    fup = FileUpload.create_fileupload_from_tus(TRANSACTION_ID, 'a.jpg')
    with db.session.begin():
        db.session.add(fup)
    fup_path = pathlib.Path(fup.get_absolute_path())
    fup_dir = fup_path.parent

    assert fup.src == f'/api/v1/fileuploads/src/{fup.guid}'

    # Delete fileupload when the file on disk is already deleted
    fup_path.unlink()
    fup.delete()


def test_fileuploads_from_tus(db, flask_app, test_root, request):
    UPLOADS_DATABASE_PATH = pathlib.Path(flask_app.config.get('UPLOADS_DATABASE_PATH'))
    FILEUPLOAD_BASE_PATH = pathlib.Path(flask_app.config.get('FILEUPLOAD_BASE_PATH'))
    TRANSACTION_ID = str(uuid.uuid4())
    tus_dir = UPLOADS_DATABASE_PATH / f'trans-{TRANSACTION_ID}'
    fup_dirs = []
    fups = []

    def cleanup():
        for fup in fups:
            fup.delete()
        if tus_dir.exists():
            shutil.rmtree(tus_dir)
        for fup_dir in fup_dirs:
            if fup_dir.exists():
                shutil.rmtree(fup_dir)
        cleanup_fileuploads_directory(FILEUPLOAD_BASE_PATH)

    request.addfinalizer(cleanup)
    tus_dir = create_transaction_dir(flask_app, TRANSACTION_ID)

    # Try creating file uploads with no files
    assert FileUpload.create_fileuploads_from_tus(TRANSACTION_ID) is None

    copy_uploaded_file(test_root, 'zebra.jpg', tus_dir, 'a.jpg')
    write_uploaded_file('a.txt', tus_dir, 'abcd\n')

    fups = FileUpload.create_fileuploads_from_tus(TRANSACTION_ID)
    with db.session.begin():
        for fup in fups:
            db.session.add(fup)
    fup_paths = [pathlib.Path(fup.get_absolute_path()) for fup in fups]
    fup_dirs = [fup_path.parent for fup_path in fup_paths]
    assert len(fups) == 2
    assert all([fup_path.is_file() for fup_path in fup_paths])


def test_fileuploads_get_src(flask_app, flask_app_client, db, test_root, request):
    fup_dir = None
    FILEUPLOAD_BASE_PATH = pathlib.Path(flask_app.config.get('FILEUPLOAD_BASE_PATH'))

    def cleanup():
        if fup_dir and fup_dir.exists():
            shutil.rmtree(fup_dir)
        cleanup_fileuploads_directory(FILEUPLOAD_BASE_PATH)

    request.addfinalizer(cleanup)
    source_file = os.path.join(test_root, 'zebra.jpg')
    sz = os.path.getsize(source_file)
    fup = FileUpload.create_fileupload_from_path(source_file, copy=True)
    fup_dir = pathlib.Path(fup.get_absolute_path())
    with db.session.begin():
        db.session.add(fup)
    response = flask_app_client.get('/api/v1/fileuploads/src/' + str(fup.guid))
    response.close()  # h/t https://github.com/pallets/flask/issues/2468#issuecomment-517797518
    fup.delete()
    assert response.status_code == 200
    assert response.content_type == 'image/jpeg'
    assert response.content_length == sz


def test_modify_image(flask_app, test_root):
    with TemporaryDirectoryUUID() as td:
        test_file = copy_uploaded_file(
            test_root, 'zebra.jpg', pathlib.Path(td), 'zebra.jpg'
        )

        with Image.open(test_file) as image:
            assert image.size == (1000, 664)

        # Check crop works
        image = modify_image(str(test_file), 'crop', args=((10, 10, 20, 20),))
        assert image.size == (10, 10)

        # Check source image isn't modified
        with Image.open(test_file) as image:
            assert image.size == (1000, 664)

        # Unsupported operation
        with pytest.raises(RuntimeError):
            image = modify_image(str(test_file), 'unsupported')

        # Add target path
        image = modify_image(
            str(test_file), 'crop', args=((10, 10, 20, 20),), target_path=test_file
        )

        # Check source image is modified
        with Image.open(test_file) as image:
            assert image.size == (10, 10)
