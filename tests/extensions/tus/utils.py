# -*- coding: utf-8 -*-
"""
tus test utils
-------------
"""

from flask import current_app
import os
import shutil
import tqdm
from PIL import Image
import numpy as np
from app.extensions.tus import tus_upload_dir
from app.utils import get_stored_filename
from tests.utils import random_nonce


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
    input_image = path.split(os.sep)[-1]
    stored_image = get_stored_filename(input_image)
    shutil.copy(image_file, f'{upload_dir}/{stored_image}')
    size = os.path.getsize(image_file)
    assert size > 0
    return transaction_id, filename


def prep_randomized_tus_dir(total=100, transaction_id=None):
    if transaction_id is None:
        transaction_id = get_transaction_id()

    upload_dir = tus_upload_dir(current_app, transaction_id=transaction_id)
    if not os.path.isdir(upload_dir):
        os.mkdir(upload_dir)

    for iteration in tqdm.tqdm(list(range(total)), desc='Random Tus Images'):
        filename = '%s.jpg' % (random_nonce(32),)
        image_file = os.path.join(upload_dir, filename)
        numpy_image = np.around(np.random.rand(128, 128, 3) * 255.0).astype(np.uint8)
        Image.fromarray(numpy_image, 'RGB').save(image_file)
        size = os.path.getsize(image_file)
        assert size > 0

    return transaction_id


# should always follow the above when finished
def cleanup_tus_dir(tid):
    upload_dir = tus_upload_dir(current_app, transaction_id=tid)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)
