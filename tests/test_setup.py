# -*- coding: utf-8 -*-
import importlib
import pathlib
import tempfile
from unittest import mock

import pytest


@pytest.mark.parametrize(
    'cmd_results,version,git_revision',
    (
        (
            (
                (
                    ['git', 'rev-parse', 'HEAD'],
                    b'6ae69c6f05b78a1da5616179605ffec22b7fef89',
                ),
                (['git', 'describe', '--tag'], b'v1.0.2-9-g6ae69c6f'),
            ),
            '1.0.2+6ae69c6f',
            '6ae69c6f05b78a1da5616179605ffec22b7fef89',
        ),
        (
            (
                (
                    ['git', 'rev-parse', 'HEAD'],
                    b'78a3994530bc2b8d4c8bfc50f38d96d42694ddbf',
                ),
                (['git', 'describe', '--tag'], b'v1.0.2'),
            ),
            '1.0.2',
            '78a3994530bc2b8d4c8bfc50f38d96d42694ddbf',
        ),
    ),
)
def test_write_version_py(request, cmd_results, version, git_revision):
    with mock.patch('subprocess.Popen') as popen:

        def cmd_output(cmd, **kwargs):
            result = mock.Mock()
            for cmd_result, value in cmd_results:
                if cmd_result == cmd:
                    break
            result.communicate.return_value = [value]
            return result

        popen.side_effect = cmd_output
        version_py = pathlib.Path(tempfile.mkstemp(suffix='.py', dir='.')[1])
        request.addfinalizer(version_py.unlink)

        import setup

        importlib.reload(setup)

        setup.write_version_py(filename=str(version_py))
        module = importlib.import_module(version_py.stem)
        assert module.version == version
        assert module.git_revision == git_revision
