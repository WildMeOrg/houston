# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging
import os
import shutil
import json

from flask import current_app

# from werkzeug.utils import secure_filename, escape

from flask_restx_patched import is_extension_enabled
from app.utils import get_stored_filename

if not is_extension_enabled('tus'):
    raise RuntimeError('Tus is not enabled')


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Tus extension initialization point.
    """
    from app.extensions.tus.flask_tus_cont import TusManager

    # Ensure the upload directory exists
    uploads_directory = tus_upload_dir(app)
    if not os.path.exists(uploads_directory):
        os.makedirs(uploads_directory)
    tm = TusManager()
    tm.init_app(app, upload_url='/api/v1/tus')
    tm.upload_file_handler(_tus_file_handler)


def _tus_file_handler(upload_file_path, filename, original_filename, req, app):
    from uuid import UUID

    # these are two alternate methods: organize by asset_group, or (arbitrary/random) transaction id
    asset_group_id = None
    transaction_id = None
    if 'x-houston-asset-group-id' in req.headers:
        asset_group_id = req.headers.get('x-houston-asset-group-id')
        UUID(
            asset_group_id, version=4
        )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)
    # TODO verify asset_group? ownership? etc  possibly also "session-secret" to prevent anyone from adding to asset_group
    if 'x-tus-transaction-id' in req.headers:
        transaction_id = req.headers.get('x-tus-transaction-id')
        UUID(
            transaction_id, version=4
        )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)

    dir = os.path.join(tus_upload_dir(app), 'unknown')
    if asset_group_id is not None:
        dir = tus_upload_dir(app, git_store_guid=asset_group_id)
    elif transaction_id is not None:
        dir = tus_upload_dir(app, transaction_id=transaction_id)
    elif 'session' in req.cookies:
        dir = tus_upload_dir(
            app, session_id=str(req.cookies.get('session')).encode('utf-8')
        )

    if not os.path.exists(dir):
        os.makedirs(dir)
    log.debug('Tus finished uploading: %r in dir %r.' % (filename, dir))
    filepath = os.path.join(dir, filename)
    os.rename(upload_file_path, filepath)

    # Store the original filename as metadata next to the file
    tus_write_file_metadata(filepath, original_filename)

    return filename


def tus_get_metadata_filepath(filepath):
    path, filename = os.path.split(filepath)
    return os.path.join(path, '.%s.meta.json' % (filename,))


def tus_write_file_metadata(stored_path, input_path):

    # Store the original filename as metadata next to the file
    metadata_filepath = tus_get_metadata_filepath(stored_path)
    with open(metadata_filepath, 'w') as metadata_file:
        metadata = {
            'saved_filename': stored_path,
            'filename': input_path,
        }
        json.dump(metadata, metadata_file)


def tus_upload_dir(app, git_store_guid=None, transaction_id=None, session_id=None):
    """Returns the location to an upload directory"""
    import hashlib

    base_path = app.config.get('UPLOADS_DATABASE_PATH', None)
    # log.warning('tus_upload_dir got base_path=%r %r %r %r' % (base_path, git_store_guid, transaction_id, session_id))
    if git_store_guid is None and transaction_id is None and session_id is None:
        return base_path
    if git_store_guid is not None:
        return os.path.join(base_path, '-'.join(['sub', str(git_store_guid)]))
    if transaction_id is not None:
        from uuid import UUID

        # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)
        UUID(transaction_id, version=4)
        return os.path.join(base_path, '-'.join(['trans', transaction_id]))
    # must be session_id
    h = hashlib.sha256(session_id)
    return os.path.join(base_path, '-'.join(['session', h.hexdigest()]))


def tus_filepaths_from(
    git_store_guid=None, session_id=None, transaction_id=None, paths=None
):
    from app.utils import HoustonException

    upload_dir = tus_upload_dir(
        current_app,
        git_store_guid=git_store_guid,
        session_id=session_id,
        transaction_id=transaction_id,
    )

    log.debug(f'_tus_filepaths_from passed paths: {paths}')
    filepaths = []
    # traverse whole upload dir and take everything
    for root, dirs, files in os.walk(upload_dir):
        for path in files:
            if not path.startswith('.'):
                filepaths.append(os.path.join(upload_dir, path))

    missing_paths = []
    if paths:
        for input_path in paths:
            stored_path = get_stored_filename(input_path)

            want_path = os.path.join(upload_dir, stored_path)
            if not os.path.exists(want_path):
                missing_paths.append(input_path)
    if missing_paths:
        raise HoustonException(log, f'{missing_paths} missing from upload')

    metadatas = []
    for filepath in filepaths:
        assert os.path.exists(filepath)
        metadata_filepath = tus_get_metadata_filepath(filepath)
        if os.path.exists(metadata_filepath):
            with open(metadata_filepath, 'r') as metadata_file:
                metadata = json.load(metadata_file)
        else:
            metadata = {}
        metadatas.append(metadata)

    return filepaths, metadatas


def tus_purge(git_store_guid=None, session_id=None, transaction_id=None):
    upload_dir = tus_upload_dir(
        current_app,
        git_store_guid=git_store_guid,
        session_id=session_id,
        transaction_id=transaction_id,
    )
    shutil.rmtree(upload_dir)
