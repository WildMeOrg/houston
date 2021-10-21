# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging
import os
import shutil

from flask import current_app


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
    tm.init_app(app, upload_url='/api/v1/asset_groups/tus')
    tm.upload_file_handler(_tus_file_handler)


def _tus_file_handler(upload_file_path, filename, req, app):
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
        dir = tus_upload_dir(app, asset_group_guid=asset_group_id)
    elif transaction_id is not None:
        dir = tus_upload_dir(app, transaction_id=transaction_id)
    elif 'session' in req.cookies:
        dir = tus_upload_dir(
            app, session_id=str(req.cookies.get('session')).encode('utf-8')
        )

    if not os.path.exists(dir):
        os.makedirs(dir)
    log.info('Tus finished uploading: %r in dir %r.' % (filename, dir))
    os.rename(upload_file_path, os.path.join(dir, filename))


def tus_upload_dir(app, asset_group_guid=None, transaction_id=None, session_id=None):
    """Returns the location to an upload directory"""
    import hashlib

    base_path = app.config.get('UPLOADS_DATABASE_PATH', None)
    # log.warning('tus_upload_dir got base_path=%r %r %r %r' % (base_path, asset_group_guid, transaction_id, session_id))
    if asset_group_guid is None and transaction_id is None and session_id is None:
        return base_path
    if asset_group_guid is not None:
        return os.path.join(base_path, '-'.join(['sub', str(asset_group_guid)]))
    if transaction_id is not None:
        return os.path.join(base_path, '-'.join(['trans', transaction_id]))
    # must be session_id
    h = hashlib.sha256(session_id)
    return os.path.join(base_path, '-'.join(['session', h.hexdigest()]))


def _tus_filepaths_from(
    asset_group_guid=None, session_id=None, transaction_id=None, paths=None
):
    upload_dir = tus_upload_dir(
        current_app,
        asset_group_guid=asset_group_guid,
        session_id=session_id,
        transaction_id=transaction_id,
    )
    log.debug('_tus_filepaths_from passed paths=%r' % (paths))
    filepaths = []
    if paths is None:  # traverse who upload dir and take everything
        for root, dirs, files in os.walk(upload_dir):
            for path in files:
                filepaths.append(os.path.join(upload_dir, path))
    else:
        if len(paths) < 1:
            return None
        for path in paths:
            want_path = os.path.join(upload_dir, path)
            assert os.path.exists(want_path), f'{want_path} does not exist'
            filepaths.append(want_path)

    return filepaths


def _tus_purge(asset_group_guid=None, session_id=None, transaction_id=None):
    upload_dir = tus_upload_dir(
        current_app,
        asset_group_guid=asset_group_guid,
        session_id=session_id,
        transaction_id=transaction_id,
    )
    shutil.rmtree(upload_dir)
