# -*- coding: utf-8 -*-
"""
FileUploads database models
--------------------
"""

from flask import current_app
from app.extensions import db, HoustonModel

import logging
import uuid
import os
import shutil

log = logging.getLogger(__name__)


# TODO move these to common tus area, possibly new extension (as suggested by jp) related to "file acquisition"
#   also, resolve overlap with submission.import_tus_files ... which prob should be moved to same new area!


def _tus_filepath_from(transaction_id, path):  # singular path, one filepath returned
    filepaths = _tus_filepaths_from(transaction_id, paths=[path])
    if filepaths is None or len(filepaths) < 1:
        return None
    return filepaths[0]


def _tus_filepaths_from(transaction_id, paths=None):
    from app.extensions.tus import tus_upload_dir

    upload_dir = tus_upload_dir(current_app, transaction_id=transaction_id)
    log.debug('_tus_filepaths_from passed paths=%r' % (paths))
    filepaths = []
    if isinstance(paths, list):
        if len(paths) < 1:
            return None
        for path in paths:
            want_path = os.path.join(upload_dir, path)
            assert os.path.exists(want_path)
            filepaths.append(want_path)

    else:  # traverse who upload dir and take everything
        for root, dirs, files in os.walk(upload_dir):
            for path in files:
                filepaths.append(os.path.join(upload_dir, path))

    return filepaths


def _tus_purge(transaction_id):
    from app.extensions.tus import tus_upload_dir

    upload_dir = tus_upload_dir(current_app, transaction_id=transaction_id)
    shutil.rmtree(upload_dir)


class FileUpload(db.Model, HoustonModel):
    """
    FileUploads database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    mime_type = db.Column(db.String, index=True, nullable=False)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'mime_type="{self.mime_type}", '
            'absolute_path="{abspath}", '
            ')>'.format(
                class_name=self.__class__.__name__,
                self=self,
                abspath=self.get_absolute_path(),
            )
        )

    def delete(self):
        filepath = self.get_absolute_path()
        with db.session.begin():
            db.session.delete(self)
        if os.path.exists(filepath):
            os.remove(filepath)

    # this is singular, so single (tus)path required
    #   note: this is 'path' from { transaction_id, path } in tus args.  sorry so many things called path.
    @classmethod
    def create_fileupload_from_tus(cls, transaction_id, path):
        assert transaction_id is not None
        assert path is not None
        source_path = _tus_filepath_from(transaction_id, path)
        fup = FileUpload.create_fileupload_from_path(source_path)
        _tus_purge(transaction_id)
        return fup

    # plural paths is optional (will do all files in dir if skipped)
    @classmethod
    def create_fileuploads_from_tus(cls, transaction_id, paths=None):
        assert transaction_id is not None
        source_paths = _tus_filepaths_from(transaction_id, paths)
        if source_paths is None or len(source_paths) < 1:
            return None
        fups = []
        for source_path in source_paths:
            fups.append(FileUpload.create_fileupload_from_path(source_path))
        _tus_purge(transaction_id)
        return fups

    @classmethod
    # default behavior is to *move*
    def create_fileupload_from_path(cls, source_path, copy=False):
        assert source_path is not None
        fup = FileUpload()
        if copy:
            fup.copy_from_path(source_path)
        else:
            fup.move_from_path(source_path)
        return fup

    def copy_from_path(self, source_path):
        assert os.path.getsize(source_path) > 0
        log.debug(
            'copy_from_path: %r to %r for %r'
            % (
                source_path,
                self.get_absolute_path(),
                self,
            )
        )
        os.makedirs(self.dirname(), exist_ok=True)
        shutil.copyfile(source_path, self.get_absolute_path())
        self.derive_mime_type()

    def move_from_path(self, source_path):
        assert os.path.getsize(source_path) > 0
        log.debug(
            'move_from_path: %r to %r for %r'
            % (
                source_path,
                self.get_absolute_path(),
                self,
            )
        )
        os.makedirs(os.path.dirname(self.get_absolute_path()), exist_ok=True)
        shutil.move(source_path, self.get_absolute_path())
        self.derive_mime_type()

    # note: this may not exist (we may just need it as a target for copy/move)
    def get_absolute_path(self):
        base_path = current_app.config.get('FILEUPLOAD_BASE_PATH', None)
        assert base_path is not None
        assert self.guid is not None
        user_path = '00000000-0000-0000-0000-000000000000'  # for owner-less
        if self.owner is not None:
            user_path = str(self.owner.guid)
        return os.path.join(base_path, user_path, str(self.guid))

    def dirname(self):
        return os.path.dirname(self.get_absolute_path())

    @property
    def src(self):
        return '/api/v1/fileuploads/src/%s' % (str(self.guid),)

    def derive_mime_type(self):
        import magic

        self.mime_type = magic.from_file(self.get_absolute_path(), mime=True)
