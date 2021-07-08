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

# In order to support sightings backref we must import the model definitions for sightings here
from app.modules.sightings import models as sightings_models  # NOQA

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
    )  # must be unique for (AssetGroup.guid, asset.filesystem_guid)
    content_guid = db.Column(db.GUID, nullable=True)

    title = db.Column(db.String(length=128), nullable=True)
    description = db.Column(db.String(length=255), nullable=True)

    meta = db.Column(db.JSON, nullable=True)

    asset_group_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group.guid', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    asset_group = db.relationship('AssetGroup', backref=db.backref('assets'))

    asset_sightings = db.relationship('SightingAssets', back_populates='asset')

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'path={self.path}, '
            'filesystem_guid={self.filesystem_guid}, '
            'semantic_guid={self.semantic_guid}, '
            'mime="{self.mime_type}", '
            'asset_group_guid="{self.asset_group_guid}", '
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

    def is_detection(self):
        # only checks at the granularity of any asset in the asset group in the detection stage
        return self.asset_group.is_detection_in_progress()

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
            'asset_groups',
            str(self.asset_group.guid),
            '_assets',
            self.get_filename(),
        )
        return relpath

    def get_symlink(self):
        asset_group_abspath = self.asset_group.get_absolute_path()
        assets_path = os.path.join(asset_group_abspath, '_assets')
        asset_symlink_filepath = os.path.join(assets_path, self.get_filename())
        return asset_symlink_filepath

    def get_derived_path(self):
        asset_group_abspath = self.asset_group.get_absolute_path()
        assets_path = os.path.join(asset_group_abspath, '_assets')
        asset_symlink_filepath = os.path.join(assets_path, 'derived', self.get_filename())
        return asset_symlink_filepath

    def update_symlink(self, asset_asset_group_filepath):
        assert os.path.exists(asset_asset_group_filepath)

        asset_symlink_filepath = self.get_symlink()
        if os.path.exists(asset_symlink_filepath):
            os.remove(asset_symlink_filepath)

        asset_group_abspath = self.asset_group.get_absolute_path()
        asset_asset_group_filepath_relative = asset_asset_group_filepath.replace(
            asset_group_abspath, '..'
        )
        os.symlink(asset_asset_group_filepath_relative, asset_symlink_filepath)
        assert os.path.exists(asset_symlink_filepath)
        assert os.path.islink(asset_symlink_filepath)

        return asset_symlink_filepath

    def mime_type_major(self):
        if not self.mime_type:
            return None
        parts = self.mime_type.split('/')
        return parts[0]

    def is_mime_type_major(self, major):
        return self.mime_type_major() == major

    # will only set .meta values that can be derived automatically from file
    # (will not overwrite any manual/other values); silently fails if unknown type for deriving
    #
    #  TODO - this now is a very basic stub -- it is operating on original file and *very* likely fails
    #  due to exif/orientation info
    def set_derived_meta(self):
        if not self.is_mime_type_major('image'):
            return None
        dmeta = {}
        source_path = self.get_symlink()
        assert os.path.exists(source_path)
        with Image.open(source_path) as im:
            size = im.size
            dmeta['width'] = size[0]
            dmeta['height'] = size[1]
        meta = self.meta if self.meta else {}
        meta['derived'] = dmeta
        self.meta = meta
        log.debug(f'setting meta.derived to {dmeta}')
        return dmeta

    # right now we _only_ use `derived` values, so not much logic here
    # TODO alter when we allow ways to override derived (or have more complex logic based on orientation)
    def get_dimensions(self):
        if not self.meta or not self.meta['derived']:
            return None
        return {
            'width': self.meta['derived'].get('width', None),
            'height': self.meta['derived'].get('height', None),
        }

    @property
    def dimensions(self):
        return self.get_dimensions()

    def get_or_make_format_path(self, format):
        FORMAT = {
            'master': [4096, 4096],
            'mid': [1024, 1024],
            'thumb': [256, 256],
        }
        assert format in FORMAT
        target_path = '.'.join(
            [os.path.splitext(self.get_derived_path())[0], format, 'jpg']
        )
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
        target_path = self.get_derived_path()
        if not os.path.exists(os.path.dirname(target_path)):
            os.mkdir(os.path.dirname(target_path))
        target_path = '.'.join([os.path.splitext(target_path)[0], 'master', 'jpg'])
        if os.path.exists(target_path):
            return target_path
        log.info('make_master_format() creating master format as %r' % (target_path,))
        with Image.open(source_path) as source_image:
            source_image.thumbnail(
                (4096, 4096)
            )  # TODO get from more global FORMAT re: above
            rgb = source_image.convert('RGB')
            rgb.save(target_path)
        return target_path

    def delete(self):
        asset_group = self.asset_group
        with db.session.begin(subtransactions=True):
            for annotation in self.annotations:
                annotation.delete()
            for sighting in self.asset_sightings:
                db.session.delete(sighting)
            db.session.delete(self)
        db.session.refresh(asset_group)
        asset_group.justify_existence()

    @classmethod
    def find(cls, guid):
        if not guid:
            return None
        return cls.query.get(guid)
