# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import datetime
import json
import logging
import os
import pathlib
import shutil
import time

import humanize
from flask import current_app
from flask_login import current_user

import app.extensions.logging as AuditLog
from app.utils import get_stored_filename
from flask_restx_patched import is_extension_enabled

# from werkzeug.utils import secure_filename, escape


if not is_extension_enabled('tus'):
    raise RuntimeError('Tus is not enabled')


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


PREFIXES = {
    'transaction': 'trans',
    'submission': 'sub',
    'session': 'session',
}


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
    tm.upload_file_handler(_tus_upload_file_handler)
    tm.delete_file_handler(_tus_delete_file_handler)
    tm.pending_transaction_handler(_tus_pending_transaction_handler)


def _tus_upload_file_handler(
    upload_file_path, filename, original_filename, resource_id, req, app
):
    from uuid import UUID

    # these are two alternate methods: organize by asset_group, or (arbitrary/random) transaction id
    # asset_group_id = None
    # if 'x-houston-asset-group-id' in req.headers:
    #     asset_group_id = req.headers.get('x-houston-asset-group-id')
    #     UUID(
    #         asset_group_id, version=4
    #     )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)
    # # TODO verify asset_group? ownership? etc  possibly also "session-secret" to prevent anyone from adding to asset_group

    transaction_id = None
    if 'x-tus-transaction-id' in req.headers:
        transaction_id = req.headers.get('x-tus-transaction-id')
        UUID(
            transaction_id, version=4
        )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)

    dir = os.path.join(tus_upload_dir(app), 'unknown')
    # if asset_group_id is not None:
    #     dir = tus_upload_dir(app, git_store_guid=asset_group_id)
    if transaction_id is not None:
        dir = tus_upload_dir(app, transaction_id=transaction_id)
    elif 'session' in req.cookies:
        dir = tus_upload_dir(
            app, session_id=str(req.cookies.get('session')).encode('utf-8')
        )

    if not os.path.exists(dir):
        os.makedirs(dir)

    metadata_filepath = tus_get_transaction_metadata_filepath(dir)

    if not os.path.exists(metadata_filepath):
        with open(metadata_filepath, 'w') as metadata_file:
            metadata = {
                'user_guid': None
                if current_user.is_anonymous
                else str(current_user.guid),
            }
            json.dump(metadata, metadata_file)

    filepath = os.path.join(dir, filename)

    max_files = int(app.config.get('TUS_MAX_FILES_PER_TRANSACTION', 5000))
    max_time = datetime.timedelta(
        seconds=int(app.config.get('TUS_MAX_TIME_PER_TRANSACTION', 60 * 60 * 24))
    )
    files = list(pathlib.Path(dir).glob('.*.metadata.json'))
    if files:
        earliest_file_mtime = min(int(os.stat(f).st_mtime) for f in files)
        transaction_time = datetime.timedelta(
            seconds=int(time.time()) - earliest_file_mtime
        )
    else:
        transaction_time = datetime.timedelta(seconds=0)

    if transaction_time >= max_time:
        raise Exception(
            f'Exceeded maximum time ({humanize.naturaldelta(max_time)}) in one transaction by {humanize.naturaldelta(transaction_time - max_time)}'
        )
    if len(files) >= max_files:
        raise Exception(
            f'Exceeded maximum number of files in one transaction: {max_files}'
        )

    try:
        os.rename(upload_file_path, filepath)

        # Store the original filename as metadata next to the file
        tus_write_file_metadata(filepath, original_filename, resource_id)
    except Exception:
        if os.path.exists(filepath):
            os.rename(filepath, upload_file_path)
        raise

    log.debug('Tus finished uploading: {!r} in dir {!r}.'.format(filename, dir))

    return filename


def _tus_delete_file_handler(upload_file_path, resource_id, req, app):
    from uuid import UUID

    # asset_group_id = None
    # if 'x-houston-asset-group-id' in req.headers:
    #     asset_group_id = req.headers.get('x-houston-asset-group-id')
    #     UUID(
    #         asset_group_id, version=4
    #     )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)
    # # TODO verify asset_group? ownership? etc  possibly also "session-secret" to prevent anyone from adding to asset_group

    transaction_id = None
    if 'x-tus-transaction-id' in req.headers:
        transaction_id = req.headers.get('x-tus-transaction-id')
        UUID(
            transaction_id, version=4
        )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)

    dir = os.path.join(tus_upload_dir(app), 'unknown')
    # if asset_group_id is not None:
    #     dir = tus_upload_dir(app, git_store_guid=asset_group_id)
    if transaction_id is not None:
        dir = tus_upload_dir(app, transaction_id=transaction_id)
    elif 'session' in req.cookies:
        dir = tus_upload_dir(
            app, session_id=str(req.cookies.get('session')).encode('utf-8')
        )

    filepaths = []
    # traverse whole upload dir and take everything
    for root, dirs, files in os.walk(dir):
        for path in files:
            if not path.startswith('.'):
                filepaths.append(os.path.join(root, path))

    matches = []
    for filepath in filepaths:
        assert os.path.exists(filepath)
        metadata_filepath = tus_get_resource_metadata_filepath(filepath)
        if os.path.exists(metadata_filepath):
            with open(metadata_filepath, 'r') as metadata_file:
                metadata = json.load(metadata_file)
                if resource_id == metadata.get('resource_id'):
                    matches.append(filepath)
                    matches.append(metadata_filepath)

    AuditLog.audit_log(
        log,
        'User requested deletion of uploaded resource ID %r, removing %d related files from transaction'
        % (
            resource_id,
            len(matches),
        ),
    )

    for match in matches:
        os.remove(match)


def _tus_pending_transaction_handler(upload_folder, req, app):
    import uuid

    assert not current_user.is_anonymous
    assert isinstance(current_user.guid, uuid.UUID)

    transaction_datas = []
    # traverse whole upload dir and take everything
    for root, dirs, files in os.walk(upload_folder):
        for dir in dirs:
            if not dir.startswith('.'):
                for key, prefix in PREFIXES.items():
                    if key not in ['transaction']:
                        continue
                    prefix_str = '%s-' % (prefix)
                    if dir.startswith(prefix_str):
                        transaction_datas.append(
                            (
                                os.path.join(root, dir),
                                dir.replace(prefix_str, ''),
                            )
                        )

    matches = []
    for transaction_data in transaction_datas:
        dir, transaction_id = transaction_data

        metadata_filepath = tus_get_transaction_metadata_filepath(dir)

        if os.path.exists(metadata_filepath):
            with open(metadata_filepath, 'r') as metadata_file:
                metadata = json.load(metadata_file)
                if str(current_user.guid) == metadata.get('user_guid'):
                    matches.append(transaction_data)

    response = {}

    log.debug(
        'User has %d pending transaction IDs: %r'
        % (
            len(matches),
            matches,
        )
    )
    for upload_dir, transaction_id in matches:

        metadata_filepath = tus_get_transaction_metadata_filepath(upload_dir)

        metadatas = []
        resources = []
        for root, dirs, files in os.walk(upload_dir):
            for path in files:
                if os.path.join(root, path) == metadata_filepath:
                    continue
                elif path.startswith('.'):
                    metadatas.append(os.path.join(root, path))
                else:
                    resources.append(os.path.join(root, path))

        valid_metadatas = []
        valid_resources = []
        for resource in resources:
            metadata = tus_get_resource_metadata_filepath(resource)
            if metadata in metadatas:
                valid_resources.append(resource)
                valid_metadatas.append(metadata)

        delete_metadatas = sorted(set(metadatas) - set(valid_metadatas))
        delete_resources = sorted(set(resources) - set(valid_resources))
        delete_files = delete_metadatas + delete_resources

        # Clean-up any corrupted data from the transaction
        if len(delete_files) > 0:
            log.debug(
                'Cleaning %d corrupted files in transaction ID %r'
                % (
                    len(delete_files),
                    transaction_id,
                )
            )

            for delete_file in delete_files:
                os.remove(delete_file)

        assert len(valid_resources) == len(valid_metadatas)
        if len(valid_resources) > 0:
            response[transaction_id] = {'resources': {}}
            total_size = 0
            changed_times = []
            for valid_resource, valid_metadata in zip(valid_resources, valid_metadatas):
                with open(valid_metadata, 'r') as metadata_file:
                    metadata = json.load(metadata_file)
                    resource_id = metadata.get('resource_id', None)
                    filename = metadata.get('filename', None)
                    if None in [resource_id, filename]:
                        continue
                    stats = os.stat(valid_resource)
                    response[transaction_id]['resources'][resource_id] = {
                        'filename': filename,
                        'bytes': stats.st_size,
                    }
                    total_size += stats.st_size
                    changed_times.append(stats.st_ctime)
            response[transaction_id]['bytes'] = total_size
            response[transaction_id]['time'] = int(min(changed_times))

    response_json = json.dumps(response)
    return response_json


def tus_get_resource_metadata_filepath(filepath):
    path, filename = os.path.split(filepath)
    return os.path.join(path, '.{}.metadata.json'.format(filename))


def tus_get_transaction_metadata_filepath(dir):
    return os.path.join(dir, '.metadata.json')


def tus_write_file_metadata(stored_path, input_path, resource_id=None):

    # Store the original filename as metadata next to the file
    metadata_filepath = tus_get_resource_metadata_filepath(stored_path)
    with open(metadata_filepath, 'w') as metadata_file:
        metadata = {
            'saved_filename': stored_path,
            'filename': input_path,
            'resource_id': resource_id,
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
        return os.path.join(
            base_path, '-'.join([PREFIXES['submission'], str(git_store_guid)])
        )
    if transaction_id is not None:
        from uuid import UUID

        # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)
        UUID(transaction_id, version=4)
        return os.path.join(
            base_path, '-'.join([PREFIXES['transaction'], transaction_id])
        )
    # must be session_id
    h = hashlib.sha256(session_id)
    return os.path.join(base_path, '-'.join([PREFIXES['session'], h.hexdigest()]))


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

    if not os.path.exists(upload_dir):
        raise OSError('Upload_dir = {!r} is missing'.format(upload_dir))

    log.debug(f'_tus_filepaths_from passed paths: {paths}')
    filepaths = []
    # traverse whole upload dir and take everything
    for root, dirs, files in os.walk(upload_dir):
        for path in files:
            if not path.startswith('.'):
                filepaths.append(os.path.join(root, path))

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
        metadata_filepath = tus_get_resource_metadata_filepath(filepath)
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
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)


def tus_cleanup():
    import datetime

    tus_directory = tus_upload_dir(current_app)

    ttl_seconds = current_app.config.get('UPLOADS_TTL_SECONDS', None)
    if ttl_seconds is None:
        return

    log.info(
        'Using clean-up TTL seconds (config UPLOADS_TTL_SECONDS) of %d' % (ttl_seconds,)
    )

    limit = int(time.time() - ttl_seconds)

    for root, dirs, files in os.walk(tus_directory):
        for path in dirs + files:
            tus_path = os.path.join(root, path)
            stats = os.stat(tus_path)
            delta = limit - stats.st_mtime
            if delta > 0:
                log.info(
                    'Deleting too old (%s seconds) Tus pending file: %r'
                    % (
                        int(delta),
                        tus_path,
                    )
                )
                if os.path.isdir(tus_path):
                    shutil.rmtree(tus_path)
                else:
                    os.remove(tus_path)
            else:
                age = int(time.time() - stats.st_mtime)

                log.info(
                    'Skipping Tus pending file (Age: %s, Remaining: %s): %r'
                    % (
                        humanize.naturaldelta(datetime.timedelta(seconds=age)),
                        humanize.naturaldelta(datetime.timedelta(seconds=-delta)),
                        tus_path,
                    )
                )

        # Only inspect the root folder, no need to check recursively
        break
