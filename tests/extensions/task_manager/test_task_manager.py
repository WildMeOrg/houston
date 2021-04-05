# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,missing-docstring
import time
import pytest


@pytest.mark.skip("doesn't currently work")
def test_task_manager(flask_app):
    from app.extensions.task_manager import TaskManager

    valueSet = False

    class TestWrapper(object):
        def periodic_callback(self):
            breakpoint()
            nonlocal valueSet
            valueSet = True

    wrapper = TestWrapper()

    TaskManager.register_callback(1, wrapper.periodic_callback)
    time.sleep(120)
    assert valueSet
