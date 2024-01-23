# -*- coding: utf-8 -*-
"""
Assets database models
--------------------
"""
import logging
import os
import pathlib
import uuid
from functools import total_ordering

from flask import current_app, url_for
from flask_login import current_user
from PIL import Image

import app.extensions.logging as AuditLog
from app.extensions import HoustonModel, SageModel, db
from app.modules import is_module_enabled, module_required
from app.modules.users.models import User
from app.utils import HoustonException

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class AssetTags(db.Model, HoustonModel):
    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)
    tag_guid = db.Column(
        db.GUID, db.ForeignKey('keyword.guid', ondelete='CASCADE'), primary_key=True
    )
    asset = db.relationship('Asset', back_populates='tag_refs')
    tag = db.relationship('Keyword')


@total_ordering
class Asset(db.Model, HoustonModel, SageModel):
    """
    Assets database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

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
        'abox': [1024, 1024],
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

    @classmethod
    def run_integrity(cls):
        from app.modules.asset_groups.models import AssetGroup

        result = {
            'no_content_guid': [],
            'multiple_sightings': [],
            'no_sightings': [],
            'file_not_on_disk': [],
        }

        # Assets must have a content guid unless they are in an AGS that is still detecting
        no_contents = Asset.query.filter(Asset.content_guid.is_(None)).all()
        for asset in no_contents:
            if isinstance(asset.git_store, AssetGroup):
                if not asset.is_detection():
                    result['no_content_guid'].append(asset.guid)
            else:
                result['no_content_guid'].append(asset.guid)

        # This will be glacial as all assets should have annots right?
        # but if there's a query foo that can give this, it's a mystery.
        # First filter should be assets with multi annots that have an encounter
        has_annots = Asset.query.filter(Asset.annotations.any()).all()
        for asset in has_annots:
            if len(asset.annotations) > 1:
                sighting = None
                for annot in asset.annotations:
                    annot_sighting = annot.get_sighting()
                    if not annot_sighting:
                        continue

                    if sighting:
                        if sighting != annot_sighting:
                            result['multiple_sightings'].append(asset.guid)
                            break
                    else:
                        sighting = annot_sighting

        # This shoudl leave us with assets that are definitely a problem and some that might be OK if they are in
        # an Asset group that has not been fully processed. Need to manually go though them to check.
        assets_without_sighting = [
            asset
            for asset in (
                db.session.query(Asset).filter(~Asset.asset_sightings.any()).all()
            )
        ]
        for asset in assets_without_sighting:
            if isinstance(asset.git_store, AssetGroup):
                if asset.git_store.is_processed():
                    # if group is processed, then this was left hanging, definitely a problem
                    result['no_sightings'].append(asset.guid)
                elif not asset.git_store.get_asset_group_sightings_for_asset(asset):
                    # asset has no ags, That's a problem
                    result['no_sightings'].append(asset.guid)
            else:
                # Not an asset group, definitely a problem
                result['no_sightings'].append(asset.guid)

        all_assets = Asset.query.all()
        for asset in all_assets:
            if not asset.file_exists_on_disk():
                result['file_not_on_disk'].append(asset.guid)

        return result

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.assets.schemas import DetailedAssetTableSchema

        return DetailedAssetTableSchema

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

    # In MWS users assigned to a task can also write to the asset
    def user_can_write(self, user):
        if is_module_enabled('missions'):
            for task_assoc in self.mission_task_participations:
                if user in task_assoc.mission_task.assigned_users:
                    return True
        return False

    def get_tags(self):
        return sorted(ref.tag for ref in self.tag_refs)

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
        return url_for(
            'api.assets_asset_src_u_by_id_2', asset_guid=str(self.guid), _external=False
        )

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

    @module_required('sightings', resolve='quiet', default=[])
    def get_asset_sightings(self):
        return self.asset_sightings

    @module_required('asset_groups', resolve='warn', default=[])
    def get_asset_group_sightings(self):
        return self.git_store.get_asset_group_sightings_for_asset(self)

    @classmethod
    def get_sage_sync_tags(cls):
        return 'asset', 'image'

    def sync_with_sage(self, ensure=False, force=False, bulk_sage_uuids=None, **kwargs):
        from app.extensions.sage import from_sage_uuid

        if self.mime_type not in current_app.config.get(
            'SAGE_MIME_TYPE_WHITELIST_EXTENSIONS', []
        ):
            log.info(
                'Cannot sync Asset %r with unsupported SAGE MIME type %r, skipping'
                % (
                    self,
                    self.mime_type,
                )
            )
            return

        if force:
            with db.session.begin(subtransactions=True):
                self.content_guid = None
                db.session.merge(self)
            db.session.refresh(self)

        if ensure:
            if self.content_guid is not None:
                if bulk_sage_uuids is not None:
                    # Existence checks can be slow one-by-one, bulk checks are better
                    if self.content_guid in bulk_sage_uuids.get('asset', {}):
                        # We have found this Asset on Sage, simply return
                        return
                else:
                    content_guid_str = str(self.content_guid)
                    sage_rowids = current_app.sage.request_passthrough_result(
                        'asset.exists', 'get', args=content_guid_str, target='sync'
                    )
                    if len(sage_rowids) == 1 and sage_rowids[0] is not None:
                        # We have found this Asset on Sage, simply return
                        return

                # If we have arrived here, it means we have a non-NULL content guid that isn't on the Sage instance
                # Null out the local content GUID and restart
                with db.session.begin(subtransactions=True):
                    self.content_guid = None
                    db.session.merge(self)
                db.session.refresh(self)

        if self.content_guid is not None:
            return

        assert self.content_guid is None
        symlink = self.get_symlink()
        image_filepath = symlink.resolve()
        if os.path.exists(image_filepath):
            try:
                with open(image_filepath, 'rb') as image_file:
                    files = {
                        'image': image_file,
                    }
                    sage_response = current_app.sage.request_passthrough_result(
                        'asset.upload', 'post', {'files': files}, target='sync'
                    )
                    sage_guid = from_sage_uuid(sage_response)

                    with db.session.begin(subtransactions=True):
                        self.content_guid = sage_guid
                        db.session.merge(self)
                    db.session.refresh(self)
            except Exception:
                message = f'Asset {self} is corrupted or an incompatible type, cannot send to Sage'
                AuditLog.audit_log_object_error(log, self, message)
                log.error(message)

        else:
            message = f'Asset {self} is missing on disk, cannot send to Sage'
            AuditLog.audit_log_object_error(log, self, message)
            log.error(message)

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
        filename = f'{self.guid}.{format}.{self.DERIVED_EXTENSION}'
        return git_store_path / '_derived' / filename

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

    def file_exists_on_disk(self):
        symlink = self.get_symlink()
        image_filepath = symlink.resolve()
        return os.path.exists(image_filepath)

    def mime_type_major(self):
        if not self.mime_type:
            return None
        parts = self.mime_type.split('/')
        return parts[0]

    def is_mime_type_major(self, major):
        return self.mime_type_major() == major

    # Special access to the raw file only for internal users
    def user_raw_read(self, user):
        # return self.is_detection() and user.is_internal
        return user.is_internal

    # This relates to if the user can access to viewing an asset if it was specifically in a sighting's ID result that the user has access to view
    def user_can_access(self, user=None):
        from app.modules.annotations.models import Annotation
        from app.modules.users.permissions.rules import ObjectActionRule
        from app.modules.users.permissions.types import AccessOperation

        if user is None:
            user = current_user

        users = []
        users.append(user)
        for collaboration in user.get_collaboration_associations():
            users.append(collaboration.get_other_user())

        sightings = []
        for user in users:
            sightings += user.get_sightings()

        annotation_guids = []
        for sighting in sightings:
            rule = ObjectActionRule(sighting, AccessOperation.READ, user)
            if rule.check():
                annotation_guids += sighting.get_matched_annotation_guids()

        annotation_guids = sorted(set(annotation_guids))

        cls = Annotation
        asset_guids = (
            cls.query.filter(cls.guid.in_(annotation_guids))
            .with_entities(cls.asset_guid)
            .all()
        )
        asset_guids = [val[0] for val in asset_guids]
        asset_guids = sorted(set(asset_guids))

        return self.guid in asset_guids

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
        return url_for(
            'api.assets_asset_src_u_by_id_2', asset_guid=self.guid, _external=True
        )

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
            if format == 'abox':
                source_image = self.draw_annotations(source_image)
            source_image.save(target_path)

        return target_path

    # currently only works with boxy annotations and theta=0
    def draw_annotations(self, image):
        if not self.annotations:
            return image
        # math assumes same aspect ratio, so if you squish an image, you change this code
        iw, ih = image.size
        dim = self.get_dimensions()
        if not dim or not dim.get('width'):
            raise ValueError('unable to get original dimensions')
        scale = iw / dim['width']
        res_image = image
        for ann in self.annotations:
            rect = ann.bounds.get('rect')
            if not rect:
                continue
            res_image = self.draw_box(res_image, [int(scale * v) for v in rect])
        return res_image

    def draw_box(self, image, rect):
        from PIL import ImageDraw  # noqa

        # h/t https://stackoverflow.com/a/43620169 for this wack ish
        overlay = Image.new('RGBA', image.size, (255, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        shape = [(rect[0], rect[1]), (rect[0] + rect[2], rect[1] + rect[3])]
        # hardcoding color for now
        draw.rectangle(shape, outline='#FF952C', fill=(255, 0, 0, 0), width=5)
        res_image = image.convert('RGBA')
        res_image = Image.alpha_composite(res_image, overlay)
        return res_image.convert('RGB')

    def rotate(self, angle, **kwargs):
        if angle % 360 == 0:
            # Nothing to do
            return
        with Image.open(self.get_symlink()) as im:
            if (angle % 360) in (90, 180, 270):
                method = getattr(Image.Transpose, f'ROTATE_{angle}')
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
                log,
                f'Unable to find valid format to save modified Asset {self.guid}',
                obj=self,
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
                obj=self,
            )
        target_path = self.get_derived_path('master')
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            return target_path
        log.info(
            'make_master_format() creating master format as {!r}'.format(target_path)
        )
        with Image.open(source_path) as source_image:
            source_image.thumbnail(self.FORMATS['master'])
            rgb = source_image.convert('RGB')
            rgb.save(target_path)
        return target_path

    def delete_relationships(self, delete_unreferenced_tags=True):
        for annotation in self.annotations:
            annotation.delete()

        for sighting in self.get_asset_sightings():
            db.session.delete(sighting)

        tags = []
        while self.tag_refs:
            ref = self.tag_refs.pop()
            # this is actually removing the AssetTags refs (not actual Keywords)
            db.session.delete(ref)
            tags.append(ref.tag)

        if delete_unreferenced_tags:
            for tag in tags:
                tag.delete_if_unreferenced()
        else:
            return tags

    # Delete of an asset as part of deletion of git_store
    def delete_cascade(self):
        with db.session.begin(subtransactions=True):
            self.delete_relationships()
            db.session.delete(self)

    # delete not part of asset group deletion so must inform asset group that we're gone
    def delete(self, justify_git_store=True):
        self.delete_cascade()

        if justify_git_store:
            db.session.refresh(self.git_store)
            self.git_store.justify_existence()
        else:
            return self.git_store

    @classmethod
    def find(cls, guid):
        if not guid:
            return None
        return cls.query.get(guid)

    def user_is_owner(self, user: User) -> bool:
        # Asset has no owner, but it has one git_store that has an owner
        return self.git_store.user_is_owner(user)

    def get_owner(self):
        return self.git_store.owner
