# -*- coding: utf-8 -*-
"""
Assets database models
--------------------
"""
# from flask import current_app
from functools import total_ordering
import os

from app.extensions import db, HoustonModel
from PIL import Image

import uuid
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@total_ordering
class Asset(db.Model, HoustonModel):
    """
    Assets database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    extension = db.Column(db.String, index=True, nullable=False)
    path = db.Column(db.String, index=True, nullable=False)

    mime_type = db.Column(db.String, index=True, nullable=False)
    magic_signature = db.Column(db.String, nullable=False)

    size_bytes = db.Column(db.BigInteger)

    filesystem_xxhash64 = db.Column(db.String, nullable=False)
    filesystem_guid = db.Column(db.GUID, nullable=False)
    semantic_guid = db.Column(
        db.GUID, nullable=False, unique=True
    )  # must be unique for (submission.guid, asset.filesystem_guid)
    content_guid = db.Column(db.GUID, nullable=True)

    title = db.Column(db.String(length=128), nullable=True)
    description = db.Column(db.String(length=255), nullable=True)

    meta = db.Column(db.JSON, nullable=True)

    submission_guid = db.Column(
        db.GUID,
        db.ForeignKey('submission.guid', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    submission = db.relationship('Submission', backref=db.backref('assets'))

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'filesystem_guid={self.filesystem_guid}, '
            'semantic_guid={self.semantic_guid}, '
            'mime="{self.mime_type}", '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def __eq__(self, other):
        return self.guid == other.guid

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        return str(self.guid) < str(other.guid)

    def __hash__(self):
        return hash(self.guid)

    @property
    def src(self):
        return '/api/v1/assets/src/%s' % (str(self.guid),)

    # this is actual (local) asset filename, not "original" (via user) filename (see: get_original_filename() below)
    def get_filename(self):
        return '%s.%s' % (
            self.guid,
            self.extension,
        )

    # this property is so that schema can output { "filename": "original_filename.jpg" }
    @property
    def filename(self):
        return self.get_original_filename()

    def get_original_filename(self):
        return os.path.basename(self.path)

    def get_relative_path(self):
        relpath = os.path.join(
            'submissions',
            str(self.submission.guid),
            '_assets',
            self.get_filename(),
        )
        return relpath

    def get_symlink(self):
        submission_abspath = self.submission.get_absolute_path()
        assets_path = os.path.join(submission_abspath, '_assets')
        asset_symlink_filepath = os.path.join(assets_path, self.get_filename())
        return asset_symlink_filepath

    def update_symlink(self, asset_submission_filepath):
        assert os.path.exists(asset_submission_filepath)

        asset_symlink_filepath = self.get_symlink()
        if os.path.exists(asset_symlink_filepath):
            os.remove(asset_symlink_filepath)

        submission_abspath = self.submission.get_absolute_path()
        asset_submission_filepath_relative = asset_submission_filepath.replace(
            submission_abspath, '..'
        )
        os.symlink(asset_submission_filepath_relative, asset_symlink_filepath)
        assert os.path.exists(asset_symlink_filepath)
        assert os.path.islink(asset_symlink_filepath)

        return asset_symlink_filepath

    def get_or_make_format_path(self, format):
        FORMAT = {
            'master': [4096, 4096],
            'mid': [1024, 1024],
            'thumb': [256, 256],
        }
        assert format in FORMAT
        target_path = '.'.join([os.path.splitext(self.get_symlink())[0], format, 'jpg'])
        if os.path.exists(target_path):
            return target_path
        log.info(
            'get_or_make_format_path() attempting to create format %r as %r'
            % (
                format,
                target_path,
            )
        )

        # we make all non-master images _from_ master format (where we assume more work will be done?
        source_path = self.get_or_make_master_format_path()
        if format == 'master':  # if so, we are done!
            return source_path

        with Image.open(source_path) as source_image:
            source_image.thumbnail(FORMAT[format])
            source_image.save(target_path)

        return target_path

    # note: Image seems to *strip exif* sufficiently here (tested with gps, comments, etc) so this may be enough!
    # also note: this fails horribly in terms of exif orientation.  wom-womp
    def get_or_make_master_format_path(self):
        source_path = self.get_symlink()
        assert os.path.exists(source_path)
        target_path = '.'.join([os.path.splitext(source_path)[0], 'master', 'jpg'])
        if os.path.exists(target_path):
            return target_path
        log.info('make_master_format() creating master format as %r' % (target_path,))
        with Image.open(source_path) as source_image:
            source_image.thumbnail(
                (4096, 4096)
            )  # TODO get from more global FORMAT re: above
            source_image.save(target_path)
        return target_path

    def delete(self):
        with db.session.begin():
            db.session.delete(self)
