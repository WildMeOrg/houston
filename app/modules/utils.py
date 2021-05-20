# -*- coding: utf-8 -*-
from pathlib import Path
from typing import NoReturn, Optional, Union
from app.extensions.api import abort
from flask import Blueprint, Flask, current_app

import logging

from uuid import UUID
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


def is_valid_guid(guid):
    try:
        _ = UUID(guid, version=4)  # pylint: disable=W0612,W0641
    except ValueError:
        return False
    return True


# Many module resources create things and then need to clean up when it fails. This helper class cleans up
class Cleanup(object):
    def __init__(self, name):
        self.name = name
        # For things where a guid has been created on EDM but not an object in Houston
        self.allocated_guids = []
        # Real things, that must have a delete method
        self.allocated_objs = []

    def add_guid(self, guid, obj_type):
        self.allocated_guids.append({'guid': guid, 'type': obj_type})

    def add_object(self, obj):
        self.allocated_objs.append(obj)

    def rollback_and_abort(
        self,
        message='Unknown error',
        log_message=None,
        status_code=400,
        error_fields=None,
    ):
        from app.modules.sightings.models import Sighting

        if log_message is None:
            log_message = message
        log.error(
            f'Bailing on {self.name} creation: {log_message} (error_fields {error_fields})'
        )

        for alloc_guid in self.allocated_guids:
            if alloc_guid['type'] == Sighting:
                guid = alloc_guid['guid']
                log.warning(f'Cleanup removing Sighting {guid} from EDM ')
                Sighting.delete_from_edm_by_guid(current_app, guid)

        for alloc_obj in self.allocated_objs:
            log.warning('Cleanup removing %r' % alloc_obj)
            alloc_obj.delete()

        abort(status_code, message, errorFields=error_fields)
