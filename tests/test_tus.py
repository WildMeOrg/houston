# -*- coding: utf-8 -*-
import base64
import pathlib
import shutil
import time
import urllib.parse
import uuid
from unittest import mock

import pytest

from app.extensions import tus
from tests.extensions.tus import utils
from tests.utils import get_stored_path, redis_unavailable


def get_file_upload_filename():
    return 'a.txt'


def get_file_upload_path(flask_app, transaction_id):
    uploads = pathlib.Path(flask_app.config['UPLOADS_DATABASE_PATH'])
    path = uploads / f'trans-{transaction_id}' / get_file_upload_filename()
    return path


def test_tus_options(flask_app_client):
    response = flask_app_client.options('/api/v1/tus')
    assert response.status_code in (200, 204)
    assert response.headers['Tus-Resumable'] == '1.0.0'
    assert int(response.headers['Tus-Max-Size']) > 0
    assert '1.0.0' in response.headers['Tus-Version'].split(',')
    assert 'creation' in response.headers['Tus-Extension'].split(',')
    assert response.data == b''


@pytest.mark.skipif(redis_unavailable(), reason='Redis unavailable')
def test_tus_upload_protocol(flask_app, flask_app_client, request):
    resource_id = str(uuid.uuid4())
    transaction_id = str(uuid.uuid4())
    file_upload_path = get_file_upload_path(flask_app, transaction_id)
    file_upload_dir = file_upload_path.parent
    request.addfinalizer(lambda: shutil.rmtree(file_upload_dir))

    # Initialize file upload
    a_txt = 'abcd\n'
    filename = file_upload_path.name
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')
    response = flask_app_client.post(
        '/api/v1/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Upload-Length': len(a_txt),
            'Tus-Resumable': '1.0.0',
            'x-tus-resource-id': resource_id,
        },
    )
    assert response.status_code == 201
    assert response.data == b''

    path = urllib.parse.urlparse(response.headers['Location']).path
    assert path.startswith('/api/v1/tus/')

    # Get file state on server
    response = flask_app_client.head(
        path,
        headers={
            'Tus-Resumable': '1.0.0',
        },
    )
    assert response.status_code == 200
    assert response.headers['Upload-Offset'] == '0'
    assert response.headers['Upload-Length'] == str(len(a_txt))
    assert response.data == b''

    # Upload part of the file
    response = flask_app_client.patch(
        path,
        headers={
            'Tus-Resumable': '1.0.0',
            'Content-Type': 'application/offset+octet-stream',
            'Content-Length': len(a_txt),
            'Upload-Offset': 0,
            'x-tus-transaction-id': transaction_id,
        },
        data=a_txt[:-1],
    )
    assert response.status_code == 204
    assert response.headers['Upload-Offset'] == str(len(a_txt) - 1)
    assert response.data == b''

    # Get file state on server
    response = flask_app_client.head(
        path,
        headers={'Tus-Resumable': '1.0.0'},
    )
    assert response.status_code == 200
    assert response.headers['Upload-Offset'] == str(len(a_txt) - 1)
    assert response.headers['Upload-Length'] == str(len(a_txt))
    assert response.data == b''

    # Set maximum number of files per transaction to 3
    flask_app.config['TUS_MAX_FILES_PER_TRANSACTION'] = 3
    request.addfinalizer(lambda: flask_app.config.pop('TUS_MAX_FILES_PER_TRANSACTION'))

    # Upload the rest of the file
    response = flask_app_client.patch(
        path,
        headers={
            'Tus-Resumable': '1.0.0',
            'Content-Type': 'application/offset+octet-stream',
            'Content-Length': len(a_txt),
            'Upload-Offset': len(a_txt) - 1,
            'x-tus-transaction-id': transaction_id,
        },
        data=a_txt[-1:],
    )
    assert response.status_code == 204
    assert response.headers['Upload-Offset'] == str(len(a_txt))
    assert response.data == b''

    stored_path = get_stored_path(file_upload_path)
    with open(stored_path) as f:
        assert f.read() == a_txt

    # After file is uploaded, we cannot use the path anymore
    response = flask_app_client.head(
        path,
        headers={'Tus-Resumable': '1.0.0'},
    )
    assert response.status_code == 404

    # Upload more files
    for response in utils.upload_files_to_tus(
        flask_app_client,
        transaction_id,
        (
            ('xyz.txt', 'xyz\n'),
            ('stu.txt', 'stu\n'),
        ),
    ):
        assert response.status_code == 204
    file_content = []
    for path in file_upload_dir.glob('[0-9a-f]*'):
        with path.open() as f:
            file_content.append(f.read())
    file_content.sort()
    assert file_content == ['abcd\n', 'stu\n', 'xyz\n']

    # After 3 files, file number limit is reached
    for response in utils.upload_files_to_tus(
        flask_app_client, transaction_id, (('ghi.txt', 'ghi\n'),)
    ):
        assert response.status_code == 400
        assert response.json == {
            'status': 400,
            'message': 'Exceeded maximum number of files in one transaction: 3',
        }
    file_content = []
    for path in file_upload_dir.glob('[0-9a-f]*'):
        with path.open() as f:
            file_content.append(f.read())
    file_content.sort()
    assert file_content == ['abcd\n', 'stu\n', 'xyz\n']

    # Delete 1 file and test max transaction time limit
    path = list(file_upload_dir.glob('[0-9a-f]*'))[0]
    pathlib.Path(tus.tus_get_resource_metadata_filepath(path)).unlink()
    path.unlink()

    with mock.patch('app.extensions.tus.time') as mock_time:
        mock_time.time.return_value = time.time() + 24 * 60 * 60 + 60
        for response in utils.upload_files_to_tus(
            flask_app_client, transaction_id, (('ghi.txt', 'ghi\n'),)
        ):
            assert response.status_code == 400
            assert response.json == {
                'status': 400,
                'message': 'Exceeded maximum time (a day) in one transaction by a minute',
            }

        mock_time.time.return_value = time.time() + 23 * 60 * 60
        for response in utils.upload_files_to_tus(
            flask_app_client, transaction_id, (('ghi.txt', 'ghi\n'),)
        ):
            assert response.status_code == 204

    assert len(list(file_upload_dir.glob('[0-9a-f]*'))) == 3


@pytest.mark.skipif(redis_unavailable(), reason='Redis unavailable')
def test_tus_delete(flask_app, flask_app_client):
    # Initialize file upload
    a_txt = 'abcd\n'

    transaction_id = str(uuid.uuid4())
    file_upload_path = get_file_upload_path(flask_app, transaction_id)

    filename = file_upload_path.name
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')
    response = flask_app_client.post(
        '/api/v1/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Upload-Length': len(a_txt),
            'Tus-Resumable': '1.0.0',
        },
    )
    assert response.status_code == 201

    path = urllib.parse.urlparse(response.headers['Location']).path
    filename = path.split('/')[-1]
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')

    # Check that the file exists on the server
    response = flask_app_client.get(
        '/api/v1/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
        },
    )
    assert response.status_code == 200
    assert response.headers['Tus-File-Name'] == filename
    assert response.headers['Tus-File-Exists'] == 'True'

    # Upload part of the file
    response = flask_app_client.patch(
        path,
        headers={
            'Tus-Resumable': '1.0.0',
            'Content-Type': 'application/offset+octet-stream',
            'Content-Length': len(a_txt),
            'Upload-Offset': 0,
        },
        data=a_txt[:-1],
    )
    assert response.status_code == 204

    # Delete file
    response = flask_app_client.delete(
        path,
        headers={
            'Tus-Resumable': '1.0.0',
            'Content-Length': 0,
        },
    )
    assert response.status_code == 204
    assert response.data == b''

    # Check that the file is deleted on the server
    response = flask_app_client.get(
        '/api/v1/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
        },
    )
    assert response.status_code == 200
    assert response.headers['Tus-File-Exists'] == 'False'

    if file_upload_path.parent.exists():
        shutil.rmtree(file_upload_path.parent)


@pytest.mark.skipif(redis_unavailable(), reason='Redis unavailable')
def test_tus_corner_cases(flask_app, flask_app_client):
    a_txt = 'abcd\n'
    filename = get_file_upload_filename()
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')

    # No Upload-Metadata and Tus-Resumable when initializing file upload
    response = flask_app_client.post(
        '/api/v1/tus',
        headers={
            'Upload-Length': len(a_txt),
        },
    )
    assert response.status_code == 500
    assert response.data == b'Received File upload for unsupported file transfer protocol'

    # Initialize file upload (Add X-Forwarded-Proto)
    response = flask_app_client.post(
        '/api/v1/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Upload-Length': len(a_txt),
            'Tus-Resumable': '1.0.0',
        },
    )
    assert response.status_code == 201
    assert response.headers['Location'].startswith('http://localhost:84/api/v1/tus/')

    path = urllib.parse.urlparse(response.headers['Location']).path
    filename = path.split('/')[-1]
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')

    # OPTIONS with Upload-Metadata and Access-Control-Request-Method
    response = flask_app_client.options(
        '/api/v1/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Access-Control-Request-Method': 'POST',
        },
    )
    assert response.status_code == 200

    # GET /api/v1/tus without sending Upload-Metadata
    response = flask_app_client.get('/api/v1/tus')
    assert response.status_code == 404
    assert response.data == b'metadata filename is not set'

    # Upload the file without a asset_group id
    response = flask_app_client.patch(
        path,
        headers={
            'Tus-Resumable': '1.0.0',
            'Content-Type': 'application/offset+octet-stream',
            'Content-Length': len(a_txt),
            'Upload-Offset': 0,
        },
        data=a_txt,
    )
    assert response.status_code == 204

    upload_dir = pathlib.Path(flask_app.config['UPLOADS_DATABASE_PATH'])
    found_one = False
    from app.utils import get_stored_filename

    stored_filename = get_stored_filename(get_file_upload_filename())
    for fname in upload_dir.glob(f'session-*/{stored_filename}'):
        uploaded_file = pathlib.Path(fname)
        with uploaded_file.open('r') as f:
            if f.read() == a_txt:
                found_one = True
                shutil.rmtree(uploaded_file.parent)
    assert found_one, 'Could not find uploaded file'
