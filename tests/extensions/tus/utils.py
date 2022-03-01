# -*- coding: utf-8 -*-
"""
tus test utils
-------------
"""

from flask import current_app
import os
import shutil
from app.extensions.tus import tus_upload_dir
from werkzeug.utils import secure_filename


def get_transaction_id():
    return '11111111-1111-1111-1111-111111111111'


def prep_tus_dir(test_root, transaction_id=None, filename='zebra.jpg'):
    if transaction_id is None:
        transaction_id = get_transaction_id()

    image_file = os.path.join(test_root, filename)

    upload_dir = tus_upload_dir(current_app, transaction_id=transaction_id)
    if not os.path.isdir(upload_dir):
        os.mkdir(upload_dir)

    # This is what the _tus_filepaths_from does so need to simulate it
    path = os.path.normpath(image_file)
    insecure_image = path.split(os.sep)[-1]
    secure_image = secure_filename(insecure_image)
    shutil.copy(image_file, f'{upload_dir}/{secure_image}')
    size = os.path.getsize(image_file)
    assert size > 0
    return transaction_id, filename


# should always follow the above when finished
def cleanup_tus_dir(tid):
    upload_dir = tus_upload_dir(current_app, transaction_id=tid)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)
