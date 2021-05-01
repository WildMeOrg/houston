# -*- coding: utf-8 -*-
from pathlib import Path
from typing import NoReturn, Optional, Union

from flask import Blueprint, Flask


def fail_on_missing_static_folder(
    app: Union[Flask, Blueprint], specific_file: Optional[str] = None
) -> NoReturn:
    """Fail when the given an ``app`` (or blueprint) that has reference
    to a static folder that does not exist.
    Optionally also check for the given ``specific_file`` relative to the static folder.
    Failure to find the folder and file will result in a ``RuntimeError``.

    """
    folder = Path(app.static_folder)
    exists = folder.exists()
    if specific_file is not None:
        exists = exists and (folder / specific_file).exists()
    if not exists:
        raise RuntimeError(
            f'static folder improperly configured - could not locate a valid installation at: {folder}'
        )
