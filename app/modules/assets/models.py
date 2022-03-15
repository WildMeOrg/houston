# -*- coding: utf-8 -*-
"""
Assets database models
--------------------
"""
from flask import current_app
from functools import total_ordering
import pathlib

from app.extensions import db, HoustonModel
from app.modules import module_required
from app.utils import HoustonException

from PIL import Image

import uuid
import logging


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AssetTags(db.Model, HoustonModel):
    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)
    tag_guid = db.Column(db.GUID, db.ForeignKey('keyword.guid'), primary_key=True)
    asset = db.relationship('Asset', back_populates='tag_refs')
    tag = db.relationship('Keyword')


@total_ordering
class Asset(db.Model, HoustonModel):
    """
    Assets database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

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

    git_store_guid = db.Column(
        db.GUID,
        db.ForeignKey('git_store.guid', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )

    git_store = db.relationship(
        'GitStore',
        backref=db.backref(
            'assets',
            primaryjoin='GitStore.guid == Asset.git_store_guid',
            order_by='Asset.guid',
        ),
    )

    annotations = db.relationship(
        'Annotation', back_populates='asset', order_by='Annotation.guid'
    )

    tag_refs = db.relationship('AssetTags')

    line_segments = db.Column(db.JSON, nullable=True)

    classifications = db.Column(db.JSON, nullable=True)

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
            'git_store_guid="{self.git_store_guid}", '
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

    @module_required('asset_groups', resolve='warn', default=False)
    def is_detection(self):
        from app.modules.asset_groups.models import AssetGroup

        # only checks at the granularity of any asset in the asset group in the detection stage
        assert isinstance(self.git_store, AssetGroup)
        return self.git_store.is_detection_in_progress()

    @property
    def tags(self):
        return self.get_tags()

    @classmethod
    def get_jobs_for_asset(cls, asset_guid, verbose):

        asset = Asset.query.get(asset_guid)
        if not asset:
            raise HoustonException(log, f'Asset {asset_guid} not found')

        return asset.get_jobs_debug(verbose)

    @module_required('asset_groups', resolve='warn', default=False)
    def get_jobs_debug(self, verbose=True):
        jobs = []
        for ags in self.get_asset_group_sightings():
            jobs.extend(ags.get_jobs_debug(verbose))

        return jobs

    def get_tags(self):
        return sorted([ref.tag for ref in self.tag_refs])

    def add_tag(self, tag):
        with db.session.begin(subtransactions=True):
            self.add_tag_in_context(tag)

    def add_tags(self, tag_list):
        with db.session.begin():
            for tag in tag_list:
                self.add_tag_in_context(tag)

    def add_tag_in_context(self, tag):
        for ref in self.tag_refs:
            if ref.tag == tag:
                # We found the tag in the asset's existing refs, no further action needed
                return

        # If not, create the new asset-tag relationship
        rel = AssetTags(asset=self, tag=tag)
        db.session.add(rel)
        self.tag_refs.append(rel)

    def remove_tag(self, tag):
        with db.session.begin(subtransactions=True):
            self.remove_tag_in_context(tag)

    def remove_tag_in_context(self, tag):
        for ref in self.tag_refs:
            if ref.tag == tag:
                db.session.delete(ref)
                break

    @property
    def src(self):
        return '/api/v1/assets/src/%s' % (str(self.guid),)

    @property
    @module_required('annotations', resolve='warn', default=-1)
    def annotation_count(self):
        return -1 if self.annotations is None else len(self.annotations)

    @property
    @module_required('missions', resolve='warn', default=[])
    def tasks(self):
        return [
            participation.mission_task
            for participation in self.mission_task_participations
        ]

    @module_required('sightings', resolve='warn', default=[])
    def get_asset_sightings(self):
        return self.asset_sightings

    @module_required('asset_groups', resolve='warn', default=[])
    def get_asset_group_sightings(self):
        return self.git_store.get_asset_group_sightings_for_asset(self)

    # this property is so that schema can output { "filename": "original_filename.jpg" }
    @property
    def filename(self):
        return self.get_original_filename()

    @property
    def extension(self):
        asset_mime_type_whitelist = current_app.config.get(
            'ASSET_MIME_TYPE_WHITELIST_EXTENSION', []
        )
        if self.mime_type not in asset_mime_type_whitelist:
            return 'unknown'
        else:
            return asset_mime_type_whitelist[self.mime_type]

    def get_original_filename(self):
        return pathlib.Path(self.path).name

    def get_symlink(self):
        git_store_path = pathlib.Path(self.git_store.get_absolute_path())

        # this is actual (local) asset filename, not "original" (via user) filename (see: get_original_filename())
        local_asset_filename = f'{self.guid}.{self.extension}'
        return git_store_path / '_assets' / local_asset_filename

    def get_derived_path(self, format):
        git_store_path = pathlib.Path(self.git_store.get_absolute_path())
        assets_path = git_store_path / '_assets'
        filename = f'{self.guid}.{format}.{self.DERIVED_EXTENSION}'
        return assets_path / 'derived' / filename

    def update_symlink(self, asset_git_store_filepath):
        target_path = pathlib.Path(asset_git_store_filepath)
        assert target_path.exists()

        asset_symlink = self.get_symlink()
        asset_symlink.unlink(missing_ok=True)

        git_store_path = pathlib.Path(self.git_store.get_absolute_path())
        asset_symlink.symlink_to(
            pathlib.Path('..') / target_path.relative_to(git_store_path)
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

    def get_image_url(self):
        from app.utils import site_url_prefix

        return f'{site_url_prefix()}/api/v1/assets/src/{self.guid}'

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
        # As the source filename has no extension, we need to generate the format manually
        format = Image.registered_extensions().get(f'.{self.extension}', None)
        if not format:
            raise HoustonException(
                log, f'Unable to find valid format to save modified Asset {self.guid}'
            )
        image_object.save(symlink.resolve(), format=format)
        self.reset_derived_images()
        log.info(f'Rerunning detection, deleting annotations {self.annotations}')
        for annotation in self.annotations:
            annotation.delete()
        self.annotations = []
        self.git_store.asset_updated(self)

    # note: Image seems to *strip exif* sufficiently here (tested with gps, comments, etc) so this may be enough!
    # also note: this fails horribly in terms of exif orientation.  wom-womp
    def get_or_make_master_format_path(self):
        source_path = self.get_symlink()
        if not source_path.exists():
            raise HoustonException(
                log,
                'Asset does not have a valid path, needs to be within an AssetGroup',
            )
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

    # Delete of an asset as part of deletion of git_store
    def delete_cascade(self):
        with db.session.begin(subtransactions=True):
            for annotation in self.annotations:
                annotation.delete()
            for sighting in self.get_asset_sightings():
                db.session.delete(sighting)
            while self.tag_refs:
                ref = self.tag_refs.pop()
                # this is actually removing the AssetTags refs (not actual Keywords)
                db.session.delete(ref)
                ref.tag.delete_if_unreferenced()
            db.session.delete(self)

    # delete not part of asset group deletion so must inform asset group that we're gone
    def delete(self):
        self.delete_cascade()
        db.session.refresh(self.git_store)
        self.git_store.justify_existence()

    @classmethod
    def find(cls, guid):
        if not guid:
            return None
        return cls.query.get(guid)

    def user_is_owner(self, user):
        # Asset has no owner, but it has one git_store that has an owner
        return user is not None and user == self.git_store.owner
