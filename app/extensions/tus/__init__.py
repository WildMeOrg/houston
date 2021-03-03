# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging
import os

from flask import current_app


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    Tus extension initialization point.
    """
    from app.extensions.tus.flask_tus_cont import TusManager

    # Ensure the upload directory exists
    uploads_directory = app.config['UPLOADS_DATABASE_PATH']
    if not os.path.exists(uploads_directory):
        os.makedirs(uploads_directory)

    tm = TusManager()
    tm.init_app(app, upload_url='/api/v1/submissions/tus')
    tm.upload_file_handler(_tus_file_handler)


def _tus_file_handler(upload_file_path, filename, req):
    import hashlib
    from uuid import UUID

    # these are two alternate methods: organize by submission, or (arbitrary/random) transaction id
    submission_id = None
    transaction_id = None
    if 'x-houston-submission-id' in req.headers:
        submission_id = req.headers.get('x-houston-submission-id')
        UUID(
            submission_id, version=4
        )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)
    # TODO verify submission? ownership? etc  possibly also "session-secret" to prevent anyone from adding to submission
    if 'x-tus-transaction-id' in req.headers:
        transaction_id = req.headers.get('x-tus-transaction-id')
        UUID(
            transaction_id, version=4
        )  # this is just to test it is a valid uuid - will throw ValueError if not! (500 response)

    dir = os.path.join(tus_upload_dir(), 'unknown')
    if submission_id is not None:
        dir = tus_upload_dir(submission_id)
    elif transaction_id is not None:
        dir = os.path.join(tus_upload_dir(), '-'.join(['trans', transaction_id]))
    elif 'session' in req.cookies:
        h = hashlib.sha256(str(req.cookies.get('session')).encode('utf-8'))
        dir = os.path.join(tus_upload_dir(), '-'.join(['session', h.hexdigest()]))

    if not os.path.exists(dir):
        os.makedirs(dir)
    log.info('Tus finished uploading: %r in dir %r.' % (filename, dir))
    os.rename(upload_file_path, os.path.join(dir, filename))


def tus_upload_dir(guid=None):
    """Returns the location to an upload directory"""
    uploads = current_app.config['UPLOADS_DATABASE_PATH']
    if guid is None:
        return uploads
    return os.path.join(uploads, '-'.join(['sub', str(guid)]))
