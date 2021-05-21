# -*- coding: utf-8 -*-
"""
AssetGroups database models
--------------------
"""

import enum
import re
from flask import current_app
from flask_login import current_user  # NOQA
import utool as ut

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

from .metadata import CreateAssetGroupMetadata

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

    def __exit__(self, exc_type, exc_value, traceback):
        if self.repo is not None:
            self.repo.remotes.origin.set_url(self.original_url)
        if exc_type:
            return False
        return True


class AssetGroupMajorType(str, enum.Enum):
    filesystem = 'filesystem'
    archive = 'archive'
    service = 'service'
    test = 'test'

    unknown = 'unknown'
    error = 'error'
    reject = 'reject'


class AssetGroupSightingStage(str, enum.Enum):
    unknown = 'unknown'
    detection = 'detection'
    curation = 'curation'
    committed = 'committed'
    processed = 'processed'
    failed = 'failed'


# AssetGroup can have many sightings, so needs a table
class AssetGroupSighting(db.Model, HoustonModel):
    guid = db.Column(db.GUID, default=uuid.uuid4, primary_key=True)
    stage = db.Column(
        db.Enum(AssetGroupSightingStage),
        default=AssetGroupSightingStage.unknown,
        nullable=False,
    )
    asset_group_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group.guid'),
        index=True,
        nullable=False,
    )
    asset_group = db.relationship('AssetGroup', backref=db.backref('sightings'))

    # configuration metadata from the create request
    config = db.Column(db.JSON, nullable=True)

    # May have multiple jobs outstanding, store as Json obj uuid_str is key, In_progress Bool is value
    jobs = db.Column(db.JSON, nullable=True)

    def check_job_status(self, job_id):
        if str(job_id) not in self.jobs:
            log.warning(f'check_job_status called for invalid job {job_id}')
            return False

        # TODO Poll ACM to see what's happening with this job, if it's ready to handle and we missed the
        # response, process it here
        return True

    def _get_jobs(self):
        if self.jobs:
            return json.loads(self.jobs)
        else:
            return dict()

    def _set_jobs(self, jobs):
        self.jobs = json.dumps(jobs)
        with db.session.begin(subtransactions=True):
            db.session.merge(self)

    def complete(self):
        # TODO check that the jobs are all actually complete
        self.stage = AssetGroupSightingStage.processed
        with db.session.begin(subtransactions=True):
            db.session.merge(self)
        db.session.refresh(self)

    def job_complete(self, job_id):
        jobs = self._get_jobs()
        if job_id in jobs:
            jobs[job_id]['active'] = False
            self._set_jobs(jobs)
            from app.modules.job_control.models import JobControl

            JobControl.delete_job(job_id)
        else:
            log.warning(f'job_id {job_id} not found in AssetGroupSighting')

    # Noddy test function before the real thing is merged in PR 188
    def start_job(self, model):
        from app.modules.job_control.models import JobControl

        job_id = uuid.uuid4()
        jobs = self._get_jobs()
        jobs[str(job_id)] = {'model': model, 'active': True}
        self._set_jobs(jobs)

        JobControl.add_asset_group_sighting_job(job_id, self.guid)

    def delete(self):
        from app.modules.job_control.models import JobControl

        with db.session.begin(subtransactions=True):
            jobs = self._get_jobs()
            for job in jobs.keys():
                JobControl.delete_job(uuid.UUID(job))
            db.session.refresh(self)
            db.session.delete(self)


class AssetGroup(db.Model, HoustonModel):
    """
    AssetGroup database model.

    AssetGroup Structure:
        _db/asset_groups/<asset_group GUID>/
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
        db.Enum(AssetGroupMajorType),
        default=AssetGroupMajorType.unknown,
        index=True,
        nullable=False,
    )

    commit = db.Column(db.String(length=40), nullable=True, unique=True)
    commit_mime_whitelist_guid = db.Column(db.GUID, index=True, nullable=True)
    commit_houston_api_version = db.Column(db.String, index=True, nullable=True)

    description = db.Column(db.String(length=255), nullable=True)

    config = db.Column(db.JSON, nullable=True)

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    owner = db.relationship(
        'User', backref=db.backref('asset_groups'), foreign_keys=[owner_guid]
    )

    submitter_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True
    )
    submitter = db.relationship(
        'User',
        backref=db.backref('submitted_asset_groups'),
        foreign_keys=[submitter_guid],
    )

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @property
    def bulk_upload(self):
        ret_val = False
        if self.config and 'bulkUpload' in self.config:
            ret_val = self.config['bulkUpload']
        return ret_val

    @property
    def anonymous(self):
        from app.modules.users.models import User

        return self.owner is User.get_public_user()

    @property
    def mime_type_whitelist(self):
        if getattr(self, '_mime_type_whitelist', None) is None:
            asset_mime_type_whitelist = current_app.config.get(
                'ASSET_MIME_TYPE_WHITELIST', []
            )
            asset_mime_type_whitelist = sorted(list(map(str, asset_mime_type_whitelist)))

            self._mime_type_whitelist = set(asset_mime_type_whitelist)
        return self._mime_type_whitelist

    @property
    def mime_type_whitelist_guid(self):
        if getattr(self, '_mime_type_whitelist_guid', None) is None:
            self._mime_type_whitelist_guid = ut.hashable_to_uuid(
                sorted(list(self.mime_type_whitelist))
            )
            # Write mime.whitelist.<mime-type-whitelist-guid>.json
            mime_type_whitelist_mapping_filepath = os.path.join(
                current_app.config.get('PROJECT_DATABASE_PATH'),
                'mime.whitelist.%s.json' % (self._mime_type_whitelist_guid,),
            )
            if not os.path.exists(mime_type_whitelist_mapping_filepath):
                log.info(
                    'Creating new MIME whitelist manifest: %r'
                    % (mime_type_whitelist_mapping_filepath,)
                )
                with open(mime_type_whitelist_mapping_filepath, 'w') as mime_type_file:
                    mime_type_whitelist_dict = {
                        str(self._mime_type_whitelist_guid): sorted(
                            list(self.mime_type_whitelist)
                        ),
                    }
                    mime_type_file.write(json.dumps(mime_type_whitelist_dict))
        return self._mime_type_whitelist_guid

    def _ensure_repository_files(self, project):
        group_path = self.get_absolute_path()

        # AssetGroup Repo Structure:
        #     _db/assetGroup/<asset_group GUID>/
        #         - .git/
        #         - _asset_group/
        #         - - <user's uploaded data>
        #         - _assets/
        #         - - <symlinks into _asset_group/ folder> with name <asset GUID >.ext --> ../_asset_group/path/to/asset/original_name.ext
        #         - metadata.json

        if not os.path.exists(group_path):
            # Initialize local repo
            log.info('Creating asset_groups structure: %r' % (group_path,))
            os.mkdir(group_path)

        # Create the repo
        git_path = os.path.join(group_path, '.git')
        if not os.path.exists(git_path):
            repo = git.Repo.init(group_path)
            assert len(repo.remotes) == 0
            git_remote_public_name = current_app.config.get('GIT_PUBLIC_NAME', None)
            git_remote_email = current_app.config.get('GIT_EMAIL', None)
            assert None not in [git_remote_public_name, git_remote_email]
            repo.git.config('user.name', git_remote_public_name)
            repo.git.config('user.email', git_remote_email)
        else:
            repo = git.Repo(group_path)

        if project is not None:
            if len(repo.remotes) == 0:
                origin = repo.create_remote('origin', project.web_url)
            else:
                origin = repo.remotes.origin
            assert origin.url == project.web_url

        asset_group_path = os.path.join(group_path, '_asset_group')
        if not os.path.exists(asset_group_path):
            os.mkdir(asset_group_path)
        pathlib.Path(os.path.join(asset_group_path, '.touch')).touch()

        assets_path = os.path.join(group_path, '_assets')
        if not os.path.exists(assets_path):
            os.mkdir(assets_path)
        pathlib.Path(os.path.join(assets_path, '.touch')).touch()

        metatdata_path = os.path.join(group_path, 'metadata.json')
        if not os.path.exists(metatdata_path):
            with open(metatdata_path, 'w') as metatdata_file:
                json.dump({}, metatdata_file)

        with open(metatdata_path, 'r') as metatdata_file:
            group_metadata = json.load(metatdata_file)

        with open(metatdata_path, 'w') as metatdata_file:
            json.dump(group_metadata, metatdata_file)

        log.info('LOCAL  REPO: %r' % (repo.working_tree_dir,))
        log.info('REMOTE REPO: %r' % (project.web_url,))

        return repo

    def git_write_upload_file(self, upload_file):
        repo = self.ensure_repository()
        file_repo_path = os.path.join(
            repo.working_tree_dir, '_asset_group', upload_file.filename
        )
        upload_file.save(file_repo_path)
        log.info('Wrote file upload and added to local repo: %r' % (file_repo_path,))

    def git_copy_path(self, path):
        absolute_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(path):
            raise IOError('The path %r does not exist.' % (absolute_path,))

        repo = self.ensure_repository()
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

        repo = self.ensure_repository()
        repo_path = os.path.join(repo.working_tree_dir, '_asset_group')
        _, filename = os.path.split(absolute_filepath)
        repo_filepath = os.path.join(repo_path, filename)

        shutil.copyfile(absolute_filepath, repo_filepath)

        return repo_filepath

    def git_commit(self, message, realize=True, update=True, **kwargs):
        repo = self.ensure_repository()

        if realize:
            self.realize_asset_group()

        if update:
            self.update_asset_symlinks(**kwargs)

        asset_group_path = self.get_absolute_path()
        asset_group_metadata_path = os.path.join(asset_group_path, 'metadata.json')

        assert os.path.exists(asset_group_metadata_path)
        with open(asset_group_metadata_path, 'r') as asset_group_metadata_file:
            asset_group_metadata = json.load(asset_group_metadata_file)

        asset_group_metadata['commit_mime_whitelist_guid'] = str(
            self.mime_type_whitelist_guid
        )
        asset_group_metadata['commit_houston_api_version'] = str(version)

        if 'frontend_sightings_data' not in asset_group_metadata and self.config:
            metadata_request = self.config
            metadata_request['sightings'] = []
            for sighting in self.sightings:
                metadata_request['sightings'].append(sighting.config)

            asset_group_metadata['frontend_sightings_data'] = metadata_request

        with open(asset_group_metadata_path, 'w') as asset_group_metadata_file:
            json.dump(asset_group_metadata, asset_group_metadata_file)

        # repo.index.add('.gitignore')
        repo.index.add('_assets/')
        repo.index.add('_asset_group/')
        repo.index.add('metadata.json')

        commit = repo.index.commit(message)

        self.update_metadata_from_commit(commit)

    def git_push(self):
        repo = self.ensure_repository()
        assert repo is not None

        with GitLabPAT(repo):
            log.info('Pushing to authorized URL')
            repo.git.push('--set-upstream', repo.remotes.origin, repo.head.ref)
            log.info('...pushed to %s' % (repo.head.ref,))

        return repo

    def git_pull(self):
        repo = self.get_repository()
        assert repo is not None

        with GitLabPAT(repo):
            log.info('Pulling from authorized URL')
            try:
                repo.git.pull(repo.remotes.origin, repo.head.ref)
            except git.exc.GitCommandError as e:
                log.info(f'git pull failed for {self.guid}: {str(e)}')
            else:
                log.info('...pulled')

        self.update_metadata_from_repo(repo)

        return repo

    def git_clone(self, project, **kwargs):
        repo = self.get_repository()
        assert repo is None

        asset_group_abspath = self.get_absolute_path()
        gitlab_url = project.web_url

        with GitLabPAT(url=gitlab_url) as glpat:
            args = (
                gitlab_url,
                asset_group_abspath,
            )
            log.info('Cloning remote asset_group:\n\tremote: %r\n\tlocal:  %r' % args)
            glpat.repo = git.Repo.clone_from(glpat.authenticated_url, asset_group_abspath)
            log.info('...cloned')

        repo = self.get_repository()
        assert repo is not None

        self.update_metadata_from_project(project)
        self.update_metadata_from_repo(repo)

        # Traverse the repo and create Asset objects in database
        self.update_asset_symlinks(**kwargs)

        return repo

    @classmethod
    def ensure_asset_group(cls, asset_group_uuid, owner=None):
        asset_group = AssetGroup.query.get(asset_group_uuid)
        if asset_group is None:
            from app.extensions import db

            if not AssetGroup.is_on_remote(asset_group_uuid):
                return None

            if owner is None:
                owner = current_user

            asset_group = AssetGroup(
                guid=asset_group_uuid,
                owner_guid=owner.guid,
            )

            with db.session.begin():
                db.session.add(asset_group)
            db.session.refresh(asset_group)

        # Make sure that the repo for this asset group exists
        asset_group.ensure_repository()

        return asset_group

    @classmethod
    def create_from_tus(
        cls, description, owner, transaction_id, paths=None, submitter=None
    ):
        assert transaction_id is not None
        if owner is not None and not owner.is_anonymous:
            group_owner = owner
        else:
            from app.modules.users.models import User

            group_owner = User.get_public_user()
        asset_group = AssetGroup(
            major_type=AssetGroupMajorType.filesystem,
            description=description,
            owner_guid=group_owner.guid,
        )

        if submitter:
            asset_group.submitter = submitter

        with db.session.begin(subtransactions=True):
            db.session.add(asset_group)

        log.info('created asset_group %r' % asset_group)
        added = None
        try:
            added = asset_group.import_tus_files(
                transaction_id=transaction_id, paths=paths
            )
        except Exception:
            log.error(
                'create_from_tus() had problems with import_tus_files(); deleting from db and fs %r'
                % asset_group
            )
            asset_group.delete()
            raise

        log.info('asset_group imported %r' % added)
        return asset_group

    def import_tus_files(self, transaction_id=None, paths=None, purge_dir=True):
        from app.extensions.tus import _tus_filepaths_from, _tus_purge

        self.ensure_remote()

        sub_id = None if transaction_id is not None else self.guid
        asset_group_abspath = self.get_absolute_path()
        asset_group_path = os.path.join(asset_group_abspath, '_asset_group')
        paths_added = []
        num_files = 0

        for path in _tus_filepaths_from(
            asset_group_guid=sub_id, transaction_id=transaction_id, paths=paths
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
            _tus_purge(asset_group_guid=sub_id, transaction_id=transaction_id)
        return assets_added

    def realize_asset_group(self):
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

        asset_group_abspath = self.get_absolute_path()
        asset_group_path = os.path.join(asset_group_abspath, '_asset_group')
        assets_path = os.path.join(asset_group_abspath, '_assets')

        # Walk the asset_group path, looking for white-listed MIME type files
        files = []
        skipped = []
        errors = []
        walk_list = sorted(list(os.walk(asset_group_path)))
        log.info('Walking asset_group...')
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
                    if mime_type not in self.mime_type_whitelist:
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
                        'asset_group_guid': self.guid,
                    }
                    files.append(file_data)
                except Exception:
                    logging.exception('Got exception in update_asset_symlinks')
                    errors.append(filepath)

        if verbose:
            print('Processed asset files from asset_group: %r' % (self,))
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
                file_data['asset_group_guid'],
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

        # Add new or update any existing Assets found in the AssetGroup
        asset_asset_group_filepath_list = [
            file_data.pop('filepath', None) for file_data in files
        ]
        assets = []
        # TODO: slim down this DB context
        with db.session.begin(subtransactions=True):
            for file_data, asset_asset_group_filepath in zip(
                files, asset_asset_group_filepath_list
            ):
                semantic_guid = file_data.get('semantic_guid', None)
                asset = Asset.query.filter(Asset.semantic_guid == semantic_guid).first()
                if asset is None:
                    # Check if we can recycle existing GUID from symlink
                    recycle_guid = existing_filepath_guid_mapping.get(
                        asset_asset_group_filepath, None
                    )
                    if recycle_guid is not None:
                        file_data['guid'] = recycle_guid
                    # Create record if asset is new
                    asset = Asset(**file_data)
                    db.session.add(asset)
                else:
                    # Update record if Asset exists
                    for key in file_data:
                        if key in [
                            'asset_group_guid',
                            'filesystem_guid',
                            'semantic_guid',
                        ]:
                            continue
                        value = file_data[key]
                        setattr(asset, key, value)
                    db.session.merge(asset)
                assets.append(asset)

        # Update all symlinks for each Asset
        for asset, asset_asset_group_filepath in zip(
            assets, asset_asset_group_filepath_list
        ):
            db.session.refresh(asset)
            asset.update_symlink(asset_asset_group_filepath)
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

        # Get all historical and current Assets for this AssetGroup
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
                    default_major_type = AssetGroupMajorType.unknown
                    self.major_type = getattr(
                        AssetGroupMajorType, value_, default_major_type
                    )

        self.description = project.description
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

    def update_metadata_from_repo(self, repo):
        repo = self.get_repository()
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
            'commit_mime_whitelist_guid', self.mime_type_whitelist_guid
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

    def is_partially_in_stage(self, stage):
        if self.sightings:
            for sighting in self.sightings:
                if sighting.stage == stage:
                    return True
        return False

    def is_completely_in_stage(self, stage):
        if self.sightings:
            for sighting in self.sightings:
                if sighting.stage != stage:
                    return False
        else:
            # If there are no sightings, the only stages that are valid are unknown and processed
            return stage in [
                AssetGroupSightingStage.unknown,
                AssetGroupSightingStage.processed,
            ]
        return True

    def is_detection_in_progress(self):
        return self.is_partially_in_stage(AssetGroupSightingStage.detection)

    def is_processed(self):
        return self.is_completely_in_stage(AssetGroupSightingStage.processed)

    def get_asset_for_file(self, filename):
        for asset in self.assets:
            if asset.path == filename:
                return asset
        return None

    def begin_ia_pipeline(self, metadata):
        assert len(metadata.detection_configs) == 1
        assert metadata.data_processed == CreateAssetGroupMetadata.DataProcessed.complete
        import copy

        for sighting_meta in metadata.request['sightings']:
            new_sighting = AssetGroupSighting(
                asset_group_guid=self.guid,
                config=copy.deepcopy(sighting_meta),
            )
            if not metadata.detection_configs[0]:
                new_sighting.stage = AssetGroupSightingStage.curation
            else:
                new_sighting.stage = AssetGroupSightingStage.detection
                # TODO for each detection config create the required jobs in the AssetGroupSighting
                # and begin them in wbia

            with db.session.begin(subtransactions=True):
                db.session.add(new_sighting)
            self.sightings.append(new_sighting)

        # make sure the repo is created
        self.ensure_remote()

        # Store the metadata in the AssetGroup but not the sightings, that is stored on the AssetGroupSightings
        self.config = dict(metadata.request)
        del self.config['sightings']

        description = 'Adding Creation metadata'
        if metadata.description != '':
            description = metadata.description
        self.git_commit(description)

    # TODO should this blow away remote repo?  by default?
    def delete(self):
        with db.session.begin(subtransactions=True):
            for asset in self.assets:
                asset.delete()
            for sighting in self.sightings:
                sighting.delete()
        db.session.refresh(self)
        # TODO: This is potentially dangerous as it decouples the Asset deletion
        #       transaction with the AssetGroup deletion transaction, bad for rollbacks
        with db.session.begin(subtransactions=True):
            db.session.delete(self)
        self.delete_dirs()

    # stub of DEX-220 ... to be continued
    def justify_existence(self):
        if self.assets:  # we have assets, so we live on
            return
        log.warning('justify_existence() found ZERO assets, self-destructing %r' % self)
        self.delete()  # TODO will this also kill remote repo?

    @classmethod
    def delete_remote_repository(cls, guid):
        return current_app.git_backend.delete_remote_project_by_name(str(guid))

    def delete_remote(self):
        return self.__class__.delete_remote_repository(self.guid)

    def get_repository(self):
        repo_path = pathlib.Path(self.get_absolute_path())
        if (repo_path / '.git').exists():
            return git.Repo(repo_path)

    def ensure_repository(self):
        if self.get_repository():
            return self.git_pull()
        project = current_app.git_backend.get_project(str(self.guid))
        if project:
            return self.git_clone(project)
        self.ensure_remote()
        return self.get_repository()

    def ensure_remote(self, additional_tags=[]):
        project = current_app.git_backend.get_project(str(self.guid))
        if not project:
            project = current_app.git_backend.create_project(
                str(self.guid),
                self.get_absolute_path(),
                self.major_type.name,
                self.description,
                additional_tags,
            )
            self._ensure_repository_files(project)

        return project

    @classmethod
    def is_on_remote(cls, guid):
        return current_app.git_backend.is_project_on_remote(str(guid))
