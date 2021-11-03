# -*- coding: utf-8 -*-
import base64
import uuid


def upload_to_tus(session, codex_url, file_path, transaction_id=None):
    if transaction_id is None:
        transaction_id = str(uuid.uuid4())
    filename = file_path.name
    encoded_filename = base64.b64encode(filename.encode('utf-8')).decode('utf-8')

    with file_path.open('rb') as f:
        content = f.read()
    length = len(content)

    response = session.post(
        codex_url('/api/v1/asset_groups/tus'),
        headers={
            'Upload-Metadata': f'filename {encoded_filename}',
            'Upload-Length': str(length),
            'Tus-Resumable': '1.0.0',
            'x-tus-transaction-id': transaction_id,
        },
    )
    assert response.status_code == 201
    tus_url = response.headers['Location']

    response = session.patch(
        tus_url,
        headers={
            'Tus-Resumable': '1.0.0',
            'Content-Type': 'application/offset+octet-stream',
            'Content-Length': str(length),
            'Upload-Offset': '0',
            'x-tus-transaction-id': transaction_id,
        },
        data=content,
    )
    assert response.status_code == 204
    return transaction_id


def create_new_user(session, codex_url, email, password='password', **kwargs):
    data = {'email': email, 'password': password}
    data.update(kwargs)
    response = session.post(codex_url('/api/v1/users/'), json=data)
    assert response.status_code == 200
    assert response.json()['email'] == email
    return response.json()['guid']
