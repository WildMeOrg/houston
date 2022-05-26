# -*- coding: utf-8 -*-
import logging

from app.utils import sizeof
from tasks.utils import app_context_task

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@app_context_task
def cache_info(context, model=None):
    """
    Get the status of the Tus cache folder
    """
    import datetime
    import json
    import os
    import time

    import humanize
    from flask import current_app

    from app.extensions import tus
    from app.modules.users.models import User

    tus_directory = tus.tus_upload_dir(current_app)

    ttl_seconds = current_app.config.get('UPLOADS_TTL_SECONDS', None)

    limit = int(time.time() - ttl_seconds)

    num_files, num_folders = 0, 0
    size_files, size_folders = 0, 0
    for root, dirs, files in os.walk(tus_directory):
        for file in files:
            tus_path = os.path.join(root, file)

            stats = os.stat(tus_path)
            delta = limit - stats.st_mtime
            age_seconds = int(time.time() - stats.st_mtime)
            age = datetime.timedelta(seconds=age_seconds)
            size = os.path.getsize(tus_path)

            log.info(
                'Cache File:  %r (Size: %s, Age: %s)'
                % (
                    tus_path,
                    sizeof(size),
                    humanize.naturaldelta(age),
                )
            )

            if delta > 0:
                log.info(
                    '\tTus cache file is too old (%s seconds), will be deleted on next check'
                    % (delta,)
                )
            size_files += size
            num_files += 1

        owner_stats = {}
        for dir in dirs:
            tus_path = os.path.join(root, dir)

            stats = os.stat(tus_path)
            delta = limit - stats.st_mtime
            age_seconds = int(time.time() - stats.st_mtime)
            age = datetime.timedelta(seconds=age_seconds)

            metadata_filepath = tus.tus_get_transaction_metadata_filepath(tus_path)
            user_guid = None

            size = 0
            num_dir_files = 0
            for root_, dirs_, files_ in os.walk(tus_path):
                for file_ in files_:
                    tus_dir_path = os.path.join(root_, file_)
                    size += os.path.getsize(tus_dir_path)

                    if tus_dir_path == metadata_filepath:
                        if os.path.exists(metadata_filepath):
                            with open(metadata_filepath, 'r') as metadata_file:
                                metadata = json.load(metadata_file)
                                user_guid = metadata.get('user_guid', None)

                    if not file_.startswith('.'):
                        num_dir_files += 1

            user = User.query.get(user_guid)
            user_key = 'unknown' if user is None else user.email
            if user_key not in owner_stats:
                owner_stats[user_key] = {
                    'transactions': 0,
                    'size': 0,
                }
            owner_stats[user_key]['transactions'] += 1
            owner_stats[user_key]['size'] += size

            log.info(
                'Transaction: %r (Size: %s, Age: %s, Uploads: %d, Owner: %s)'
                % (
                    tus_path,
                    sizeof(size),
                    humanize.naturaldelta(age),
                    num_dir_files,
                    user.email,
                )
            )

            if delta > 0:
                log.info(
                    '\tTus transaction is too old (%s seconds), will be deleted on next check'
                    % (delta,)
                )

            size_folders += size
            num_folders += 1

        # Only inspect the root folder, no need to check recursively
        break

    for user_key in sorted(owner_stats.keys()):
        log.info(
            'User %s: %d transactions (%s)'
            % (
                user_key,
                owner_stats[user_key]['transactions'],
                sizeof(owner_stats[user_key]['size']),
            )
        )

    log.info(
        'All Cache Files: %d (%s)'
        % (
            num_files,
            sizeof(size_files),
        )
    )
    log.info(
        'All Transactions: %d (%s)'
        % (
            num_folders,
            sizeof(size_folders),
        )
    )
    log.info(
        'All Tus Cache: %d (%s)'
        % (
            num_files + num_folders,
            sizeof(size_files + size_folders),
        )
    )


@app_context_task
def cleanup(context):
    """
    Get the status of the Tus cache folder
    """
    from app.extensions import tus

    tus.tus_cleanup()
