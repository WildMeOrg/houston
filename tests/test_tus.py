# -*- coding: utf-8 -*-
import base64
import hashlib
import os
import pathlib
import re
import shutil
import urllib.parse

import pytest
import redis


@pytest.fixture
def file_upload_filename():
    return 'a.txt'


@pytest.fixture
def file_upload_submission_id():
    return '11111111-1111-1111-1111-111111111111'


@pytest.fixture
def file_upload_path(flask_app, file_upload_submission_id, file_upload_filename):
    uploads = pathlib.Path(flask_app.config['UPLOADS_DATABASE_PATH'])
    path = uploads / f'sub-{file_upload_submission_id}' / file_upload_filename
    yield path
    if path.parent.exists():
        shutil.rmtree(path.parent)


def redis_unavailable(*args):
    try:
        host = os.getenv('REDIS_HOST') or 'localhost'
        redis.Redis(host=host).get('test')
        return False
    except redis.exceptions.ConnectionError:
        return True


def test_tus_options(flask_app_client):
    response = flask_app_client.options('/api/v1/submissions/tus')
    assert response.status_code in (200, 204)
    assert response.headers['Tus-Resumable'] == '1.0.0'
    assert int(response.headers['Tus-Max-Size']) > 0
    assert '1.0.0' in response.headers['Tus-Version'].split(',')
    assert 'creation' in response.headers['Tus-Extension'].split(',')
    assert response.data == b''


@pytest.mark.skipif(redis_unavailable(), reason='Redis unavailable')
def test_tus_upload_protocol(
    flask_app_client, file_upload_path, file_upload_submission_id
):
    # Initialize file upload
    a_txt = 'abcd\n'
    filename = file_upload_path.name
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')
    response = flask_app_client.post(
        '/api/v1/submissions/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Upload-Length': len(a_txt),
            'Tus-Resumable': '1.0.0',
        },
    )
    assert response.status_code == 201
    assert response.data == b''

    path = urllib.parse.urlparse(response.headers['Location']).path
    assert path.startswith('/api/v1/submissions/tus/')

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

    # Upload the rest of the file
    response = flask_app_client.patch(
        path,
        headers={
            'Tus-Resumable': '1.0.0',
            'Content-Type': 'application/offset+octet-stream',
            'Content-Length': len(a_txt),
            'Upload-Offset': len(a_txt) - 1,
            'X-Houston-Submission-Id': file_upload_submission_id,
        },
        data=a_txt[-1:],
    )
    assert response.status_code == 204
    assert response.headers['Upload-Offset'] == str(len(a_txt))
    assert response.data == b''

    with file_upload_path.open() as f:
        assert f.read() == a_txt

    # After file is uploaded, we cannot use the path anymore
    response = flask_app_client.head(
        path,
        headers={'Tus-Resumable': '1.0.0'},
    )
    assert response.status_code == 404


@pytest.mark.skipif(redis_unavailable(), reason='Redis unavailable')
def test_tus_delete(flask_app_client, file_upload_path):
    # Initialize file upload
    a_txt = 'abcd\n'
    filename = file_upload_path.name
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')
    response = flask_app_client.post(
        '/api/v1/submissions/tus',
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
        '/api/v1/submissions/tus',
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
        '/api/v1/submissions/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
        },
    )
    assert response.status_code == 200
    assert response.headers['Tus-File-Exists'] == 'False'


@pytest.mark.skipif(redis_unavailable(), reason='Redis unavailable')
def test_tus_corner_cases(flask_app, flask_app_client, file_upload_filename):
    a_txt = 'abcd\n'
    filename = file_upload_filename
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')

    # No Upload-Metadata and Tus-Resumable when initializing file upload
    response = flask_app_client.post(
        '/api/v1/submissions/tus',
        headers={
            'Upload-Length': len(a_txt),
        },
    )
    assert response.status_code == 500
    assert response.data == b'Received File upload for unsupported file transfer protocol'

    # Initialize file upload (Add X-Forwarded-Proto)
    response = flask_app_client.post(
        '/api/v1/submissions/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Upload-Length': len(a_txt),
            'Tus-Resumable': '1.0.0',
            'X-Forwarded-Proto': 'https',
        },
    )
    assert response.status_code == 201
    assert response.headers['Location'].startswith('https://')

    path = urllib.parse.urlparse(response.headers['Location']).path
    filename = path.split('/')[-1]
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')

    # OPTIONS with Upload-Metadata and Access-Control-Request-Method
    response = flask_app_client.options(
        '/api/v1/submissions/tus',
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Access-Control-Request-Method': 'POST',
        },
    )
    assert response.status_code == 200

    # GET /api/v1/submissions/tus without sending Upload-Metadata
    response = flask_app_client.get('/api/v1/submissions/tus')
    assert response.status_code == 404
    assert response.data == b'metadata filename is not set'

    # Upload the file without a submission id
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

    session = re.search('session=([^;]*)', response.headers['Set-Cookie']).group(1)
    hashed_session = hashlib.sha256(session.encode('utf-8')).hexdigest()
    upload_dir = pathlib.Path(flask_app.config['UPLOADS_DATABASE_PATH'])
    uploaded_file = upload_dir / f'session-{hashed_session}' / file_upload_filename
    with uploaded_file.open('r') as f:
        assert f.read() == a_txt
    shutil.rmtree(uploaded_file.parent)
