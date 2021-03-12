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
            log.debug('FileUpload delete removing file %r' % self.get_absolute_path())
            os.remove(filepath)

    # this is singular, so single (tus)path required
    #   note: this is 'path' from { transaction_id, path } in tus args.  sorry so many things called path.
    @classmethod
    def create_fileupload_from_tus(cls, transaction_id, path):
        from app.extensions.tus import _tus_filepaths_from, _tus_purge

        assert transaction_id is not None
        assert path is not None
        source_paths = _tus_filepaths_from(transaction_id=transaction_id, paths=[path])
        fup = FileUpload.create_fileupload_from_path(source_paths[0])
        _tus_purge(transaction_id=transaction_id)
        return fup

    # plural paths is optional (will do all files in dir if skipped)
    @classmethod
    def create_fileuploads_from_tus(cls, transaction_id, paths=None):
        from app.extensions.tus import _tus_filepaths_from, _tus_purge

        assert transaction_id is not None
        source_paths = _tus_filepaths_from(transaction_id=transaction_id, paths=paths)
        if source_paths is None or len(source_paths) < 1:
            return None
        fups = []
        for source_path in source_paths:
            fups.append(FileUpload.create_fileupload_from_path(source_path))
        _tus_purge(transaction_id=transaction_id)
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
        os.makedirs(self.get_absolute_dirname(), exist_ok=True)
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
        return os.path.join(base_path, self.relative_dirpath(), str(self.guid))

    def get_absolute_dirname(self):
        return os.path.dirname(self.get_absolute_path())

    @property
    def src(self):
        return '/api/v1/fileuploads/src/%s' % (str(self.guid),)

    def derive_mime_type(self):
        import magic

        self.mime_type = magic.from_file(self.get_absolute_path(), mime=True)

    # this is relative path, based on first 4 chars of guid, e.g. 'ab/cd' for 'abcdef01-2345-6789-abcd-ef0123456789'
    def relative_dirpath(self):
        return FileUpload.dirpath_from_guid(self.guid)

    @classmethod
    def dirpath_from_guid(cls, guid):
        assert isinstance(guid, uuid.UUID)
        s = str(guid)
        return os.path.join(s[0:2], s[2:4])
