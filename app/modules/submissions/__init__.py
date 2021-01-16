# -*- coding: utf-8 -*-
"""
Submissions module
============
"""

from app.extensions.api import api_v1
#from flask_tus_cont import TusManager
from app.extensions.submission.flask_tus_cont import TusManager
import os
import hashlib

import logging
log = logging.getLogger(__name__)

def init_app(app, **kwargs):
    # pylint: disable=unused-argument,unused-variable
    """
    Init Submissions module.
    """
    api_v1.add_oauth_scope('submissions:read', 'Provide access to Submissions details')
    api_v1.add_oauth_scope(
        'submissions:write', 'Provide write access to Submissions details'
    )

    # Touch underlying modules
    from . import models, resources  # NOQA

    api_v1.add_namespace(resources.api)

    #tus endpoint and magic here
    updir = os.path.join('_db', 'uploads')
    if not os.path.exists(updir):
        os.makedirs(updir)
    tm = TusManager()
    tm.init_app(app, upload_url='/api/v1/submissions/tus', upload_folder=str(updir))
    tm.upload_file_handler(_tus_file_handler)


def _tus_file_handler(upload_file_path, filename, req):
    submission_id = None
    if 'x-houston-submission-id' in req.headers:
        submission_id = req.headers.get('x-houston-submission-id')
    ### TODO verify submission? ownership? etc  possibly also "session-secret" to prevent anyone from adding to submission

    path = 'unknown'
    if submission_id is not None:
        path = '-'.join(['sub', submission_id])
    elif 'session' in req.cookies:
        h = hashlib.sha256(str(req.cookies.get('session')).encode('utf-8'))
        path = '-'.join(['session', h.hexdigest()])

    dir = os.path.join('_db', 'uploads', path)
    if not os.path.exists(dir):
        os.makedirs(dir)
    log.info('Tus finished uploading: %r in dir %r.' % (filename, dir))
    os.rename(upload_file_path, os.path.join(dir, filename))

