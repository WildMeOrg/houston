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
    owner_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    owner = db.relationship('User', backref=db.backref('owned_fileuploads'))

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
        # TODO cleanup file(s)
        with db.session.begin():
            db.session.delete(self)

    @classmethod
    # this is singular, so single (tus)path required
    #   note: this is 'path' from { transaction_id, path } in tus args.  sorry so many things called path.
    def create_fileupload_from_tus(cls, transaction_id, tus_path, owner):
        assert transaction_id is not None
        assert tus_path is not None
        #  do the magic here to get path to tus file
        #  source_path = tus_filepath_from( transaction_id, paths={ tus_path } )
        source_path = None  # cuz we dont have that magic!
        return FileUpload.create_fileupload_from_path(
            source_path, owner
        )  # will move (no longer in tus dir)

    @classmethod
    # default behavior is to *move*
    def create_fileupload_from_path(cls, source_path, owner, copy=False):
        assert source_path is not None
        fup = FileUpload()
        fup.owner = owner
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
        os.makedirs(os.path.dirname(self.get_absolute_path()), exist_ok=True)
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

    def derive_mime_type(self):
        import magic

        self.mime_type = magic.from_file(self.get_absolute_path(), mime=True)
