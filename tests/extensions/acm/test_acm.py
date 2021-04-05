# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring


def test_acm_initializes(flask_app):

    targets = flask_app.acm.get_target_list()
    assert targets == ['default']
