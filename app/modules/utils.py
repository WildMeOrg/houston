# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional


def fail_on_missing_static_folder(folder: str, file: Optional[str] = None):
    """Fail when the given ``folder`` does not exist.
    Optionally also check for the given ``file``.
    Failure to find the folder and file will result in a ``RuntimeError``.

    """
    folder = Path(folder)
    exists = folder.exists()
    if file is not None:
        exists = exists or file.exists()
    if not exists:
        raise RuntimeError(
            f'static folder improperly configured - could not locate a valid installation at: {folder}'
        )
