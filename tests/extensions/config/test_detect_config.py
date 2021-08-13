# -*- coding: utf-8 -*-
from tests.extensions.config import utils


def test_get_detect_config(flask_app_client):
    utils.get_and_check_detection_config(flask_app_client)
