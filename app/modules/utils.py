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
    if not isinstance(value, float):
        return False
    max_latitude = 90.0
    min_latitude = -90.0

    # Validate range
    return min_latitude <= value <= max_latitude


def is_valid_longitude(value):
    if not isinstance(value, float):
        return False
    max_longitude = 180.0
    min_longitude = -180.0

    # Validate range
    return min_longitude <= value <= max_longitude


# this is a messy one. do we want to require timezone?  do we accept
#   anything other than "full" ISO-8601?  for now just taking only full
#   date + time (seconds optional) and ignoring timezone.  ymmv / caveat emptor / etc
def is_valid_datetime_string(dtstr):
    # the 16 char is to prevent (valid 8601) date-only strings like '2001-02-03' and force a time (at least HH:MM)
    if not isinstance(dtstr, str) or len(dtstr) < 16:
        return False
    try:
        iso8601_to_datetime_generic(dtstr)
        return True
    except Exception as ex:
        log.warning(f'is_valid_datetime_string failed on {dtstr}: {str(ex)}')
    return False


# this makes no attempt to care about timezone, so beware!  it also will likely throw some kind of
#   exception -- probably ValueError -- if the input is incorrect.
#
# NOTE: there are quite a few more datetime utilites in app/utils, so check that out too!
#   in particular, related to this one is:  iso8601_to_datetime_with_timezone()
def iso8601_to_datetime_generic(iso):
    import datetime

    return datetime.datetime.fromisoformat(iso)


def is_valid_uuid_string(guid):
    if not guid or not isinstance(guid, str):
        return False
    try:
        _ = UUID(guid, version=4)  # pylint: disable=W0612,W0641
    except ValueError:
        return False
    return True
