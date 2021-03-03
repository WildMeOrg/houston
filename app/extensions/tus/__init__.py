# -*- coding: utf-8 -*-
"""
Logging adapter
---------------
"""
import logging
import os


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
    tm.init_app(app, upload_url='/api/v1/submissions/tus')
    tm.upload_file_handler(_tus_file_handler)


def _tus_file_handler(upload_file_path, filename, req, app):
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

    dir = os.path.join(tus_upload_dir(app), 'unknown')
    if submission_id is not None:
        dir = tus_upload_dir(app, submission_guid=submission_id)
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


def tus_upload_dir(app, submission_guid=None, transaction_id=None, session_id=None):
    """Returns the location to an upload directory"""
    import hashlib

    base_path = app.config.get('UPLOADS_DATABASE_PATH', None)
    # log.warn('tus_upload_dir got base_path=%r %r %r %r' % (base_path, submission_guid, transaction_id, session_id))
    if submission_guid is None and transaction_id is None and session_id is None:
        return base_path
    if submission_guid is not None:
        return os.path.join(base_path, '-'.join(['sub', str(submission_guid)]))
    if transaction_id is not None:
        return os.path.join(base_path, '-'.join(['trans', transaction_id]))
    # must be session_id
    h = hashlib.sha256(session_id)
    return os.path.join(base_path, '-'.join(['session', h.hexdigest()]))
