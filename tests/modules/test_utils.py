# -*- coding: utf-8 -*-
from unittest.mock import Mock

import pytest

from app.modules.utils import fail_on_missing_static_folder


class TestFailOnMissingStaticFolder:
    def test_passing(self, tmp_path):
        app = Mock()
        app.static_folder = tmp_path
        fail_on_missing_static_folder(app)

    def test_missing_static_folder(self):
        app = Mock()
        static_folder = '/tmp/foo/bar/baz'
        app.static_folder = static_folder
        with pytest.raises(RuntimeError, match=static_folder):
            fail_on_missing_static_folder(app)

    def test_passing_specific_file(self, tmp_path):
        app = Mock()
        app.static_folder = tmp_path
        with (tmp_path / 'foo.txt').open('w') as fb:
            fb.write('bar')
        fail_on_missing_static_folder(app, 'foo.txt')

    def test_missing_specific_file(self, tmp_path):
        app = Mock()
        app.static_folder = tmp_path
        with pytest.raises(RuntimeError, match=str(tmp_path)):
            fail_on_missing_static_folder(app, 'bar.txt')
