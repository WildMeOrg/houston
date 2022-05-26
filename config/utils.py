# -*- coding: utf-8 -*-
import importlib
import os
from pathlib import Path

from dotenv import load_dotenv

__all__ = (
    'export_dotenv',
    'import_class',
)


def import_class(import_str):
    """Import a class from a string like ``package.module:class``."""
    path, cls_name = import_str.split(':')
    module = importlib.import_module(path)
    cls = getattr(module, cls_name)
    return cls


_CWD_DOTENV = Path.cwd() / '.env'
_DEFAULT_DOTENV = Path(os.getenv('HOUSTON_DOTENV', _CWD_DOTENV))


# FIXME: This is a workaround for an invalidly set GITLAB_REMOTE_LOGIN_PAT
# unset GITLAB_REMOTE_LOGIN_PAT if empty
if 'GITLAB_REMOTE_LOGIN_PAT' in os.environ and not os.environ['GITLAB_REMOTE_LOGIN_PAT']:
    del os.environ['GITLAB_REMOTE_LOGIN_PAT']


def export_dotenv(locations=[], stop_on_found=True):
    """Load ``os.environ`` from a dotenv file to populate environment variables

    The ``locations`` list, if supplied, will be used to locate
    specifically named files.

    If ``stop_on_found`` is true, only the first resolved dotenv file
    will be used. All others in possible locations are ignored.

    """
    default = _DEFAULT_DOTENV
    locs = [Path(loc) for loc in locations] + [default]
    for loc in locs:
        if loc.exists():
            load_dotenv(str(loc), override=False)
            if stop_on_found:
                break
