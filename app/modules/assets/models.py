# -*- coding: utf-8 -*-
"""
Assets database models
--------------------
"""
# from flask import current_app
from functools import total_ordering
import pathlib

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
    asset_group = db.relationship('AssetGroup', back_populates='assets')

    asset_sightings = db.relationship(
        'SightingAssets', back_populates='asset', order_by='SightingAssets.sighting_guid'
    )

    annotations = db.relationship(
        'Annotation', back_populates='asset', order_by='Annotation.guid'
    )

    DERIVED_EXTENSION = 'jpg'
    DERIVED_MIME_TYPE = 'image/jpeg'

    FORMATS = {
        'master': [4096, 4096],
        'mid': [1024, 1024],
        'thumb': [256, 256],
    }

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
        return pathlib.Path(self.path).name

    def get_symlink(self):
        asset_group_path = pathlib.Path(self.asset_group.get_absolute_path())
        assets_path = asset_group_path / '_assets'
        return assets_path / self.get_filename()

    def get_derived_path(self, format):
        asset_group_path = pathlib.Path(self.asset_group.get_absolute_path())
        assets_path = asset_group_path / '_assets'
        filename = f'{self.guid}.{format}.{self.DERIVED_EXTENSION}'
        return assets_path / 'derived' / filename

    def update_symlink(self, asset_asset_group_filepath):
        target_path = pathlib.Path(asset_asset_group_filepath)
        assert target_path.exists()

        asset_symlink = self.get_symlink()
        asset_symlink.unlink(missing_ok=True)

        asset_group_path = pathlib.Path(self.asset_group.get_absolute_path())
        asset_symlink.symlink_to(
            pathlib.Path('..') / target_path.relative_to(asset_group_path)
        )
        assert asset_symlink.exists()
        assert asset_symlink.is_symlink()

        return asset_symlink

    def mime_type_major(self):
        if not self.mime_type:
            return None
        parts = self.mime_type.split('/')
        return parts[0]

    def is_mime_type_major(self, major):
        return self.mime_type_major() == major

    # Special access to the raw file only for internal users
    def user_raw_read(self, user):
        return self.is_detection() and user.is_internal

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
        assert source_path.exists()
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
        assert format in self.FORMATS
        target_path = self.get_derived_path(format)
        if target_path.exists():
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
            source_image.thumbnail(self.FORMATS[format])
            source_image.save(target_path)

        return target_path

    def rotate(self, angle, **kwargs):
        if angle % 360 == 0:
            # Nothing to do
            return
        with Image.open(self.get_symlink()) as im:
            if (angle % 360) in (90, 180, 270):
                method = getattr(Image, f'ROTATE_{angle}')
                im_rotated = im.transpose(method=method)
            else:
                im_rotated = im.rotate(angle, **kwargs)
        self.original_changed(im_rotated)

    def get_backup_path(self):
        symlink = self.get_symlink()
        return symlink.parent / f'.{symlink.name}'

    def get_original_path(self):
        symlink = self.get_symlink()
        backup = self.get_backup_path()
        if backup.exists():
            return backup
        return symlink

    def reset_derived_images(self):
        # Reset metadata
        self.set_derived_meta()
        # Delete derived images (generated next time they're fetched)
        for format in self.FORMATS:
            self.get_derived_path(format).unlink(missing_ok=True)

    def original_changed(self, image_object):
        # Creates a copy of the original image
        symlink = self.get_symlink()
        # Store backup in _assets/.{guid}.{ext}
        backup = self.get_backup_path()
        if not backup.exists():
            symlink.resolve().rename(backup)
        # Save the new image
        image_object.save(symlink.resolve())
        self.reset_derived_images()
        self.asset_group.asset_updated(self)

    # note: Image seems to *strip exif* sufficiently here (tested with gps, comments, etc) so this may be enough!
    # also note: this fails horribly in terms of exif orientation.  wom-womp
    def get_or_make_master_format_path(self):
        source_path = self.get_symlink()
        assert source_path.exists()
        target_path = self.get_derived_path('master')
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            return target_path
        log.info('make_master_format() creating master format as %r' % (target_path,))
        with Image.open(source_path) as source_image:
            source_image.thumbnail(self.FORMATS['master'])
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
