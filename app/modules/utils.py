# -*- coding: utf-8 -*-
import logging
from pathlib import Path
from typing import NoReturn, Optional, Union
from uuid import UUID

from flask import Blueprint, Flask

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


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


def is_valid_sex(value):
    return value is None or value in {'male', 'female', 'unknown'}


def is_valid_latitude(value):
    if not (isinstance(value, float) or isinstance(value, int)):
        return False
    max_latitude = 90.0
    min_latitude = -90.0

    # Validate range
    return min_latitude <= value <= max_latitude


def is_valid_longitude(value):
    if not (isinstance(value, float) or isinstance(value, int)):
        return False
    max_longitude = 180.0
    min_longitude = -180.0

    # Validate range
    return min_longitude <= value <= max_longitude


# This is quite robust. Timezone is mandatory. Anything else is just making our life
# difficult for ourselves in the long term
def is_valid_datetime_string(dtstr):
    # the 16 char is to prevent (valid 8601) date-only strings like '2001-02-03' and force a time (at least HH:MM)
    if not isinstance(dtstr, str) or len(dtstr) < 16:
        return False
    try:
        import datetime

        # will raise ValueError if not valid
        date_time = datetime.datetime.fromisoformat(dtstr)
        return date_time.tzinfo is not None
    except Exception:
        pass
    return False


def is_valid_uuid_string(guid):
    if not guid or not isinstance(guid, str):
        return False
    try:
        _ = UUID(guid, version=4)  # pylint: disable=W0612,W0641
    except ValueError:
        return False
    return True
