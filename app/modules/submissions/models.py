# -*- coding: utf-8 -*-
"""
Submissions database models
--------------------
"""

import enum
import re
from flask import current_app
from flask_login import current_user  # NOQA
from app.extensions import db, HoustonModel, parallel

from app.version import version

import logging
import tqdm
import uuid
import json
import git
import os
import pathlib
import shutil

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def compute_xxhash64_digest_filepath(filepath):
    try:
        import xxhash
        import os

        assert os.path.exists(filepath)

        with open(filepath, 'rb') as file_:
            digest = xxhash.xxh64_hexdigest(file_.read())
    except Exception:
        digest = None
    return digest


class GitLabPAT(object):
    def __init__(self, repo=None, url=None):
        assert repo is not None or url is not None, 'Must specify one of repo or url'

        self.repo = repo
        if url is None:
            assert repo is not None, 'both repo and url parameters provided, choose one'
            url = repo.remotes.origin.url
        self.original_url = url

        remote_personal_access_token = current_app.config.get(
            'GITLAB_REMOTE_LOGIN_PAT', None
        )
        self.authenticated_url = re.sub(
            #: match on either http or https
            r'(https?)://(.*)$',
            #: replace with basic-auth entities
            r'\1://oauth2:%s@\2' % (remote_personal_access_token,),
            self.original_url,
        )

    def __enter__(self):
        # Update remote URL with PAT
        if self.repo is not None:
            self.repo.remotes.origin.set_url(self.authenticated_url)
        return self

    def __exit__(self, type, value, traceback):
        if self.repo is not None:
            self.repo.remotes.origin.set_url(self.original_url)
        return True


class SubmissionMajorType(str, enum.Enum):
    filesystem = 'filesystem'
    archive = 'archive'
    service = 'service'
    test = 'test'

    unknown = 'unknown'
    error = 'error'
    reject = 'reject'


class Submission(db.Model, HoustonModel):
    """
    Submission database model.

    Submission Structure:
        _db/submissions/<submission GUID>/
            - .git/
            - _asset_group/
            - - <user's uploaded data>
            - _assets/
            - - <symlinks into _asset_group/ folder> with name <asset GUID >.ext --> ../_asset_group/path/to/asset/original_name.ext
            - metadata.json
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    major_type = db.Column(
        db.Enum(SubmissionMajorType),
        default=SubmissionMajorType.unknown,
        index=True,
        nullable=False,
    )

    commit = db.Column(db.String(length=40), nullable=True, unique=True)
    commit_mime_whitelist_guid = db.Column(db.GUID, index=True, nullable=True)
    commit_houston_api_version = db.Column(db.String, index=True, nullable=True)

    description = db.Column(db.String(length=255), nullable=True)

    meta = db.Column(db.JSON, nullable=True)

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    owner = db.relationship('User', backref=db.backref('submissions'))

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def git_write_upload_file(self, upload_file):
        repo = current_app.agm.create_repository(self)
        file_repo_path = os.path.join(
            repo.working_tree_dir, '_asset_group', upload_file.filename
        )
        upload_file.save(file_repo_path)
        log.info('Wrote file upload and added to local repo: %r' % (file_repo_path,))

    def git_copy_path(self, path):
        absolute_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(path):
            raise IOError('The path %r does not exist.' % (absolute_path,))

        repo = current_app.agm.get_repository(self)
        repo_path = os.path.join(repo.working_tree_dir, '_asset_group')

        absolute_path = absolute_path.rstrip('/')
        repo_path = repo_path.rstrip('/')
        absolute_path = '%s/' % (absolute_path,)
        repo_path = '%s/' % (repo_path,)

        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)

        shutil.copytree(absolute_path, repo_path)

    def git_copy_file_add(self, filepath):
        absolute_filepath = os.path.abspath(os.path.expanduser(filepath))
        if not os.path.exists(absolute_filepath):
            raise IOError('The filepath %r does not exist.' % (absolute_filepath,))

        repo = current_app.agm.get_repository(self)
        repo_path = os.path.join(repo.working_tree_dir, '_asset_group')
        _, filename = os.path.split(absolute_filepath)
        repo_filepath = os.path.join(repo_path, filename)

        shutil.copyfile(absolute_filepath, repo_filepath)

        return repo_filepath

    def git_commit(self, message, realize=True, update=True, **kwargs):
        repo = current_app.agm.get_repository(self)

        if realize:
            self.realize_submission()

        if update:
            self.update_asset_symlinks(**kwargs)

        asset_group_path = self.get_absolute_path()
        submission_metadata_path = os.path.join(asset_group_path, 'metadata.json')

        assert os.path.exists(submission_metadata_path)
        with open(submission_metadata_path, 'r') as submission_metadata_file:
            submission_metadata = json.load(submission_metadata_file)

        submission_metadata['commit_mime_whitelist_guid'] = str(
            current_app.agm.mime_type_whitelist_guid
        )
        submission_metadata['commit_houston_api_version'] = str(version)

        with open(submission_metadata_path, 'w') as submission_metadata_file:
            json.dump(submission_metadata, submission_metadata_file)

        # repo.index.add('.gitignore')
        repo.index.add('_assets/')
        repo.index.add('_asset_group/')
        repo.index.add('metadata.json')

        commit = repo.index.commit(message)

        self.update_metadata_from_commit(commit)

    def git_push(self):
        repo = current_app.agm.get_repository(self)
        assert repo is not None

        with GitLabPAT(repo):
            log.info('Pushing to authorized URL')
            repo.git.push('--set-upstream', repo.remotes.origin, repo.head.ref)
            log.info('...pushed to %s' % (repo.head.ref,))

        return repo

    def git_pull(self):
        repo = current_app.agm.get_repository(self)
        assert repo is not None

        with GitLabPAT(repo):
            log.info('Pulling from authorized URL')
            repo.git.pull(repo.remotes.origin, repo.head.ref)
            log.info('...pulled')

        self.update_metadata_from_repo(repo)

        return repo

    def git_clone(self, project, **kwargs):
        repo = current_app.agm.get_repository(self)
        assert repo is None

        submission_abspath = self.get_absolute_path()
        gitlab_url = project.web_url

        with GitLabPAT(url=gitlab_url) as glpat:
            args = (
                gitlab_url,
                submission_abspath,
            )
            log.info('Cloning remote submission:\n\tremote: %r\n\tlocal:  %r' % args)
            glpat.repo = git.Repo.clone_from(glpat.authenticated_url, submission_abspath)
            log.info('...cloned')

        repo = current_app.agm.get_repository(self)
        assert repo is not None

        self.update_metadata_from_project(project)
        self.update_metadata_from_repo(repo)

        # Traverse the repo and create Asset objects in database
        self.update_asset_symlinks(**kwargs)

        return repo

    @classmethod
    def ensure_asset_group(cls, asset_group_uuid, owner=None):
        asset_group = Submission.query.get(asset_group_uuid)
        if asset_group is None:
            from app.extensions import db

            if not current_app.agm.is_asset_group_on_remote(asset_group_uuid):
                return None

            if owner is None:
                owner = current_user

            asset_group = Submission(
                guid=asset_group_uuid,
                owner_guid=owner.guid,
            )

            with db.session.begin():
                db.session.add(asset_group)
            db.session.refresh(asset_group)

        # Make sure that the repo for this asset group exists
        if current_app.agm.get_repository(asset_group) is None:
            current_app.agm.create_repository(asset_group)

        return asset_group

    @classmethod
    def create_submission_from_tus(cls, description, owner, transaction_id, paths=None):
        assert transaction_id is not None
        submission = Submission(
            major_type=SubmissionMajorType.filesystem,
            description=description,
        )
        if owner is not None and not owner.is_anonymous:
            submission.owner = owner
        with db.session.begin(subtransactions=True):
            db.session.add(submission)

        log.info('created submission %r' % submission)
        added = None
        try:
            added = submission.import_tus_files(
                transaction_id=transaction_id, paths=paths
            )
        except Exception:
            log.error(
                'create_submission_from_tus() had problems with import_tus_files(); deleting from db and fs %r'
                % submission
            )
            submission.delete()
            raise

        log.info('submission imported %r' % added)
        return submission

    def import_tus_files(self, transaction_id=None, paths=None, purge_dir=True):
        from app.extensions.tus import _tus_filepaths_from, _tus_purge

        current_app.agm.create_repository(self)

        sub_id = None if transaction_id is not None else self.guid
        submission_abspath = self.get_absolute_path()
        asset_group_path = os.path.join(submission_abspath, '_asset_group')
        paths_added = []
        num_files = 0

        for path in _tus_filepaths_from(
            submission_guid=sub_id, transaction_id=transaction_id, paths=paths
        ):
            name = pathlib.Path(path).name
            paths_added.append(name)
            num_files += 1
            os.rename(path, os.path.join(asset_group_path, name))

        assets_added = []
        if num_files > 0:
            log.info('Tus collect for %d files moved' % (num_files))
            self.git_commit('Tus collect commit for %d files.' % (num_files,))
            self.git_push()
            for asset in self.assets:
                if asset.path in paths_added:
                    assets_added.append(asset)

        if purge_dir:
            # may have some unclaimed files in it
            _tus_purge(submission_guid=sub_id, transaction_id=transaction_id)
        return assets_added

    def realize_submission(self):
        """
        Unpack any archives and resolve any symlinks

        Must check for security vulnerabilities around decompression bombs and
        recursive links
        """
        ARCHIVE_MIME_TYPE_WHITELIST = [  # NOQA
            'application/gzip',
            'application/vnd.rar',
            'application/x-7z-compressed',
            'application/x-bzip',
            'application/x-bzip2',
            'application/x-tar',
            'application/zip',
        ]
        pass

    def update_asset_symlinks(self, verbose=True, existing_filepath_guid_mapping={}):
        """
        Traverse the files in the _asset_group/ folder and add/update symlinks
        for any relevant files we identify

        Ref:
            https://pypi.org/project/python-magic/
            https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
            http://www.iana.org/assignments/media-types/media-types.xhtml
        """
        from app.modules.assets.models import Asset
        import utool as ut
        import magic

        submission_abspath = self.get_absolute_path()
        asset_group_path = os.path.join(submission_abspath, '_asset_group')
        assets_path = os.path.join(submission_abspath, '_assets')

        # Walk the submission path, looking for white-listed MIME type files
        files = []
        skipped = []
        errors = []
        walk_list = sorted(list(os.walk(asset_group_path)))
        log.info('Walking submission...')
        for root, directories, filenames in tqdm.tqdm(walk_list):
            filenames = sorted(filenames)
            for filename in filenames:
                filepath = os.path.join(root, filename)

                # Normalize path (sanity check)
                filepath = os.path.normpath(filepath)

                # Sanity check, ensure that the path is formatted well
                assert os.path.exists(filepath)
                assert os.path.isabs(filepath)
                try:
                    basename = os.path.basename(filepath)
                    _, extension = os.path.splitext(basename)
                    extension = extension.lower()
                    extension = extension.strip('.')

                    if basename.startswith('.'):
                        # Skip hidden files
                        if basename not in ['.touch']:
                            skipped.append((filepath, basename))
                        continue

                    if os.path.isdir(filepath):
                        # Skip any directories (sanity check)
                        skipped.append((filepath, extension))
                        continue

                    if os.path.islink(filepath):
                        # Skip any symbolic links (sanity check)
                        skipped.append((filepath, extension))
                        continue
                    mime_type = magic.from_file(filepath, mime=True)
                    if mime_type not in current_app.agm.mime_type_whitelist:
                        # Skip any unsupported MIME types
                        skipped.append((filepath, extension))
                        continue

                    magic_signature = magic.from_file(filepath)
                    size_bytes = os.path.getsize(filepath)

                    file_data = {
                        'filepath': filepath,
                        'path': basename,
                        'extension': extension,
                        'mime_type': mime_type,
                        'magic_signature': magic_signature,
                        'size_bytes': size_bytes,
                        'submission_guid': self.guid,
                    }
                    files.append(file_data)
                except Exception:
                    logging.exception('Got exception in update_asset_symlinks')
                    errors.append(filepath)

        if verbose:
            print('Processed asset files from submission: %r' % (self,))
            print('\tFiles   : %d' % (len(files),))
            print('\tSkipped : %d' % (len(skipped),))
            if len(skipped) > 0:
                skipped_ext_list = [skip[1] for skip in skipped]
                skipped_ext_str = ut.repr3(ut.dict_hist(skipped_ext_list))
                skipped_ext_str = skipped_ext_str.replace('\n', '\n\t\t')
                print('\t\t%s' % (skipped_ext_str,))
            print('\tErrors  : %d' % (len(errors),))

        # Compute the xxHash64 for all found files
        filepath_list = [file_data_['filepath'] for file_data_ in files]
        arguments_list = list(zip(filepath_list))
        print('Computing filesystem xxHash64...')
        filesystem_xxhash64_list = parallel(
            compute_xxhash64_digest_filepath, arguments_list
        )
        filesystem_guid_list = list(map(ut.hashable_to_uuid, filesystem_xxhash64_list))

        # Update file_data with the filesystem and semantic hash information
        zipped = zip(files, filesystem_xxhash64_list, filesystem_guid_list)
        for file_data, filesystem_xxhash64, filesystem_guid in zipped:
            file_data['filesystem_xxhash64'] = filesystem_xxhash64
            file_data['filesystem_guid'] = filesystem_guid
            semantic_guid_data = (
                file_data['submission_guid'],
                file_data['filesystem_guid'],
            )
            file_data['semantic_guid'] = ut.hashable_to_uuid(semantic_guid_data)

        # Delete all existing symlinks
        existing_asset_symlinks = ut.glob(os.path.join(assets_path, '*'))
        for existing_asset_symlink in existing_asset_symlinks:
            basename = os.path.basename(existing_asset_symlink)
            if basename in ['.touch', 'derived']:
                continue
            existing_asset_target = os.readlink(existing_asset_symlink)
            existing_asset_target_ = os.path.abspath(
                os.path.join(assets_path, existing_asset_target)
            )
            if os.path.exists(existing_asset_target_):
                uuid_str, _ = os.path.splitext(basename)
                uuid_str = uuid_str.strip().strip('.')
                if existing_asset_target_ not in existing_filepath_guid_mapping:
                    try:
                        existing_filepath_guid_mapping[
                            existing_asset_target_
                        ] = uuid.UUID(uuid_str)
                    except Exception:
                        pass
            os.remove(existing_asset_symlink)

        # Add new or update any existing Assets found in the Submission
        asset_submission_filepath_list = [
            file_data.pop('filepath', None) for file_data in files
        ]
        assets = []
        # TODO: slim down this DB context
        with db.session.begin(subtransactions=True):
            for file_data, asset_submission_filepath in zip(
                files, asset_submission_filepath_list
            ):
                semantic_guid = file_data.get('semantic_guid', None)
                asset = Asset.query.filter(Asset.semantic_guid == semantic_guid).first()
                if asset is None:
                    # Check if we can recycle existing GUID from symlink
                    recycle_guid = existing_filepath_guid_mapping.get(
                        asset_submission_filepath, None
                    )
                    if recycle_guid is not None:
                        file_data['guid'] = recycle_guid
                    # Create record if asset is new
                    asset = Asset(**file_data)
                    db.session.add(asset)
                else:
                    # Update record if Asset exists
                    for key in file_data:
                        if key in ['submission_guid', 'filesystem_guid', 'semantic_guid']:
                            continue
                        value = file_data[key]
                        setattr(asset, key, value)
                    db.session.merge(asset)
                assets.append(asset)

        # Update all symlinks for each Asset
        for asset, asset_submission_filepath in zip(
            assets, asset_submission_filepath_list
        ):
            db.session.refresh(asset)
            asset.update_symlink(asset_submission_filepath)
            if verbose:
                print(filepath)
                print('\tAsset         : %s' % (asset,))
                print('\tSemantic GUID : %s' % (asset.semantic_guid,))
                print('\tExtension     : %s' % (asset.extension,))
                print('\tMIME type     : %s' % (asset.mime_type,))
                print('\tSignature     : %s' % (asset.magic_signature,))
                print('\tSize bytes    : %s' % (asset.size_bytes,))
                print('\tFS xxHash64   : %s' % (asset.filesystem_xxhash64,))
                print('\tFS GUID       : %s' % (asset.filesystem_guid,))

        # Get all historical and current Assets for this Submission
        db.session.refresh(self)

        # Delete any historical Assets that have been deleted from this commit
        deleted_assets = list(set(self.assets) - set(assets))
        if verbose:
            print('Deleting %d orphaned Assets' % (len(deleted_assets),))
        with db.session.begin(subtransactions=True):
            for deleted_asset in deleted_assets:
                deleted_asset.delete()
        db.session.refresh(self)

    def update_metadata_from_project(self, project):
        # Update any local metadata from sub
        for tag in project.tag_list:
            tag = tag.strip().split(':')
            if len(tag) == 2:
                key, value = tag
                key_ = key.lower()
                value_ = value.lower()
                if key_ == 'type':
                    default_major_type = SubmissionMajorType.unknown
                    self.major_type = getattr(
                        SubmissionMajorType, value_, default_major_type
                    )

        self.description = project.description
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

    def update_metadata_from_repo(self, repo):
        repo = current_app.agm.get_repository(self)
        assert repo is not None

        if len(repo.branches) > 0:
            commit = repo.branches.master.commit
            self.update_metadata_from_commit(commit)

        return repo

    def update_metadata_from_commit(self, commit):
        self.commit = commit.hexsha

        metadata_path = os.path.join(commit.repo.working_dir, 'metadata.json')
        assert os.path.exists(metadata_path)
        with open(metadata_path, 'r') as metadata_file:
            metadata_dict = json.load(metadata_file)

        self.commit_mime_whitelist_guid = metadata_dict.get(
            'commit_mime_whitelist_guid', current_app.agm.mime_type_whitelist_guid
        )
        self.commit_houston_api_version = metadata_dict.get(
            'commit_houston_api_version', version
        )

        with db.session.begin(subtransactions=True):
            db.session.merge(self)
        db.session.refresh(self)

    def get_absolute_path(self):
        asset_group_database_path = current_app.config.get(
            'ASSET_GROUP_DATABASE_PATH', None
        )
        assert asset_group_database_path is not None
        assert os.path.exists(asset_group_database_path)

        asset_group_path = os.path.join(asset_group_database_path, str(self.guid))

        return asset_group_path

    def delete_dirs(self):
        if os.path.exists(self.get_absolute_path()):
            shutil.rmtree(self.get_absolute_path())

    # TODO should this blow away remote repo?  by default?
    def delete(self):
        with db.session.begin(subtransactions=True):
            for asset in self.assets:
                asset.delete()
        db.session.refresh(self)
        # TODO: This is potentially dangerous as it decouples the Asset deletion
        #       transaction with the Submission deletion transaction, bad for rollbacks
        with db.session.begin(subtransactions=True):
            db.session.delete(self)
        self.delete_dirs()

    # stub of DEX-220 ... to be continued
    def justify_existence(self):
        if self.assets:  # we have assets, so we live on
            return
        log.warning('justify_existence() found ZERO assets, self-destructing %r' % self)
        self.delete()  # TODO will this also kill remote repo?
