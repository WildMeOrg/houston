# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Asset Curation Model (Sage) manager.

"""

import keyword
import logging
import uuid

import tqdm
from flask import current_app, render_template, request, session  # NOQA
from flask_login import current_user  # NOQA

from app.extensions.restManager.RestManager import RestManager
from app.modules import is_module_enabled
from app.utils import HoustonException
from flask_restx_patched import is_extension_enabled

if not is_extension_enabled('sage'):
    raise RuntimeError('Sage is not enabled')


KEYWORD_SET = set(keyword.kwlist)
SAGE_UNKNOWN_NAME = '____'

log = logging.getLogger(__name__)


class SageModel(object):
    """Adds `viewed` column to a derived declarative model."""

    @classmethod
    def sync_all_with_sage(cls, prune=False, **kwargs):
        houston_tag, sage_tag = cls.get_sage_sync_tags()
        sage_uuids = current_app.sage.request_passthrough_result(
            '{}.list'.format(houston_tag), 'get', target='sync'
        )
        sage_uuids = {from_sage_uuid(guid) for guid in sage_uuids}

        bulk_sage_uuids = {
            houston_tag: sage_uuids,
        }

        if houston_tag == 'annotation':
            houston_tag_ = 'asset'
            sage_uuids_ = current_app.sage.request_passthrough_result(
                '{}.list'.format(houston_tag_), 'get', target='sync'
            )
            sage_uuids_ = {from_sage_uuid(guid) for guid in sage_uuids_}
            bulk_sage_uuids[houston_tag_] = sage_uuids_

        objs = cls.query.all()
        desc = 'Sage Sync {}'.format(cls.__name__)
        for obj in tqdm.tqdm(objs, desc=desc):
            obj.sync_with_sage(bulk_sage_uuids=bulk_sage_uuids, **kwargs)

        if prune:
            houston_sage_uuids = cls.query.with_entities(cls.content_guid).all()

            # Standardize
            houston_sage_uuids = {
                guid for (guid,) in houston_sage_uuids if guid is not None
            }

            # Calculate
            delete_sage_uuids = sage_uuids - houston_sage_uuids

            if len(delete_sage_uuids) > 0:
                log.warning(
                    'Pruning %d %s records from Sage'
                    % (
                        len(delete_sage_uuids),
                        cls.__name__,
                    )
                )

                key = '{}_uuid_list'.format(sage_tag)
                sage_request = {
                    key: [],
                }
                for delete_sage_uuid in delete_sage_uuids:
                    sage_request[key].append(to_sage_uuid(delete_sage_uuid))

                sage_response = current_app.sage.request_passthrough_result(
                    '{}.delete'.format(houston_tag),
                    'delete',
                    {'json': sage_request},
                    target='sync',
                )
                assert sage_response

    @classmethod
    def get_sage_sync_tags(cls):
        raise NotImplementedError('implement this function in each class')

    def sync_with_sage(cls, **kwargs):
        raise NotImplementedError('implement this function in each class')


def to_sage_uuid(houston_guid):
    if houston_guid is None:
        return None
    if not isinstance(houston_guid, uuid.UUID):
        return None
    sage_uuid = {'__UUID__': str(houston_guid)}
    return sage_uuid


def from_sage_uuid(sage_uuid):
    if sage_uuid is None:
        return None

    assert '__UUID__' in sage_uuid, 'Received sage_uuid = {!r}'.format(sage_uuid)

    sage_guid = sage_uuid.get('__UUID__', None)
    if sage_guid is None:
        return None

    try:
        houston_guid = uuid.UUID(sage_guid)
    except Exception:
        return None

    return houston_guid


class SageManager(RestManager):
    # pylint: disable=abstract-method
    """"""
    NAME = 'SAGE'

    USE_JSON_HEADERS = False

    ENDPOINT_PREFIX = 'api'
    # We use // as a shorthand for prefix
    # fmt: off
    ENDPOINTS = {
        # No user.session, Sage doesn't support logins
        'annotation': {
            'list': '//annot/json/',
            'data': '//annot/name/uuid/json/?annot_uuid_list=[{"__UUID__": "%s"}]',
            'exists': '//annot/rowid/uuid/json/?annot_uuid_list=[{"__UUID__":"%s"}]',
            'create': '//annot/json/',
            'delete': '//annot/json/',
        },
        'asset': {
            'list': '//image/json/',
            'create': '//image/json/',
            'exists': '//image/rowid/uuid/json/?image_uuid_list=[{"__UUID__":"%s"}]',
            'upload': '//upload/image/json/',
            'delete': '//image/json/',
        },
        'version': {
            'dict': '//version/',
        },
        'engine': {
            'list': '//engine/job/status/',
            'detect': '//engine/detect/cnn/',
            'identification': '//engine/query/graph/',
            'result': '//engine/job/result/?jobid=%s',
            'status': '//engine/process/status/',
        },
    }
    # fmt: on

    def __init__(self, pre_initialize=False, *args, **kwargs):
        super(SageManager, self).__init__(pre_initialize, *args, **kwargs)

    # The sage API returns a status and a response, this processes it to raise an exception on any
    # error and provide validated parsed output for further processing
    def request_passthrough_parsed(
        self, tag, method, passthrough_kwargs=None, args=None, target='default'
    ):
        import app.extensions.logging as AuditLog  # NOQA

        if passthrough_kwargs is None:
            passthrough_kwargs = {}

        response = self.request_passthrough(
            tag, method, passthrough_kwargs, args, target=target
        )

        # Sage sent invalid response
        try:
            response_json = response.json()
        except Exception:
            message = (f'{tag} {method} failed to parse json response from Sage',)
            raise HoustonException(
                log,
                f'{message} Sage Status:{response.status_code} Reason: {response.reason}, headers: {response.headers} Text: {response.text}',
                AuditLog.AuditType.BackEndFault,
                message=message,
            )

        # Sage sent invalid response
        status_data = response_json.get('status', None)
        if not status_data:
            message = (f'{tag} {method} failed to parse json status data from Sage',)
            raise HoustonException(
                log,
                f'{message} Sage Status:{response.status_code} Sage Reason: {response.reason}',
                AuditLog.AuditType.BackEndFault,
                message=message,
            )

        # status is correctly formatted, see if it failed
        response_data = response_json.get('response', None)
        if (
            not response.ok
            or not status_data.get('success', False)
            or response.status_code != 200
            or response_data is None
        ):
            log_message = status_data.get('message', response.reason)
            #  Don't report internal Sage Errors to the frontend
            message = 'failed to send Sage request'

            status_code = response.status_code
            if status_code > 600:
                status_code = 400  # flask doesnt like us to use "invalid" codes. :(
            raise HoustonException(
                log,
                f'{tag} {method} failed {log_message} {response.status_code}',
                AuditLog.AuditType.BackEndFault,
                status_code=status_code,
                message=message,
                sage_status_code=response.status_code,
            )

        return response, response_json, response_data

    # Provides the same validation and exception raising as above but just returns the result
    def request_passthrough_result(
        self, tag, method, passthrough_kwargs=None, args=None, target='default'
    ):
        response, response_json, response_data = self.request_passthrough_parsed(
            tag, method, passthrough_kwargs, args, target=target
        )
        return response_data

    def get_job_status(self, jobs, exclude_done=False):

        statuses = {}
        sage_jobs = []
        for job_uuid in sorted(jobs.keys()):
            job_data = jobs[job_uuid]
            status = str(job_data.get('status', None))

            if status not in statuses:
                statuses[status] = 0
            statuses[status] += 1

            if exclude_done and status in [
                'completed',
                'exception',
                'corrupted',
                'None',
                None,
            ]:
                continue

            sage_jobs.append(
                (
                    job_data.get('jobcounter'),
                    job_data.get('time_received'),
                    status,
                    str(job_uuid),
                )
            )

        sage_jobs = sorted(sage_jobs)
        sage_jobs = [sage_job[2:][::-1] for sage_job in sage_jobs]

        return statuses, sage_jobs

    def sync_jobs(self, verbose=True):
        jobs = current_app.sage.request_passthrough_result(
            'engine.list', 'get', target='default'
        )['json_result']
        statuses, sage_jobs = current_app.sage.get_job_status(jobs)

        sage_completed_job_guids = {
            sage_job_id for sage_job_id, status in sage_jobs if status in ['completed']
        }
        sage_failed_job_guids = {
            sage_job_id for sage_job_id, status in sage_jobs if status in ['exception']
        }
        sage_pending_job_guids = {
            sage_job_id
            for sage_job_id, status in sage_jobs
            if status not in ['completed', 'exception', 'corrupted', 'None']
        }

        detection_active, detection_seen_jobs = self.sync_jobs_detection(
            sage_completed_job_guids,
            sage_failed_job_guids,
            sage_pending_job_guids,
            verbose=verbose,
        )
        identification_active, identification_seen_jobs = self.sync_jobs_identification(
            sage_completed_job_guids,
            sage_failed_job_guids,
            sage_pending_job_guids,
            verbose=verbose,
        )

        active = detection_active + identification_active
        seen_jobs = set(detection_seen_jobs + identification_seen_jobs)

        sage_completed_job_guids = set(sage_completed_job_guids) - set(seen_jobs)
        sage_failed_job_guids = set(sage_failed_job_guids) - set(seen_jobs)
        sage_pending_job_guids = set(sage_pending_job_guids) - set(seen_jobs)
        if verbose:
            log.info('Not Tracked Jobs')
            log.info('\tCompleted    : %d' % (len(sage_completed_job_guids),))
            log.info('\tFailed       : %d' % (len(sage_failed_job_guids),))
            log.info('\tActive       : %d' % (len(sage_pending_job_guids),))

        return active

    def sync_jobs_detection(
        self,
        sage_completed_job_guids,
        sage_failed_job_guids,
        sage_pending_job_guids,
        verbose=True,
    ):
        from app.modules.asset_groups.models import (
            AssetGroupSighting,
            AssetGroupSightingStage,
        )

        asset_group_sightings = AssetGroupSighting.query.all()

        start_keys = {'model', 'active', 'start', 'asset_guids'}
        end_keys = start_keys | {'json_result', 'end'}

        completed = 0
        fetch_jobs = []
        failed_jobs = []
        pending_jobs = []
        unknown_jobs = []
        corrupt_jobs = []
        seen_jobs = []
        for asset_group_sighting in tqdm.tqdm(asset_group_sightings):
            if asset_group_sighting.jobs:
                for job_id in asset_group_sighting.jobs:
                    job_metadata = asset_group_sighting.jobs[job_id]
                    job_data = (asset_group_sighting, job_id)

                    seen_jobs.append(job_id)

                    if job_metadata.keys() < start_keys:
                        corrupt_jobs.append(job_data)
                    elif job_metadata.get('active'):
                        if job_id in sage_completed_job_guids:
                            fetch_jobs.append(job_data)
                        elif job_id in sage_failed_job_guids:
                            failed_jobs.append(job_data)
                        elif job_id in sage_pending_job_guids:
                            pending_jobs.append(job_data)
                        else:
                            unknown_jobs.append(job_data)
                    else:
                        if job_metadata.keys() < end_keys:
                            if job_id in sage_completed_job_guids:
                                fetch_jobs.append(job_data)
                            elif job_id in sage_failed_job_guids:
                                corrupt_jobs.append(job_data)
                            elif job_id in sage_pending_job_guids:
                                corrupt_jobs.append(job_data)
                            else:
                                corrupt_jobs.append(job_data)
                        else:
                            completed += 1

        if verbose:
            log.info('Detection Jobs')
            log.info('\tCompleted    : %d' % (completed,))
            log.info('\tFailed       : %d' % (len(failed_jobs),))
            log.info('\tActive       : %d' % (len(pending_jobs),))
            log.info('\tFetch Results: %d' % (len(fetch_jobs),))
            log.info('\tMissing      : %d' % (len(unknown_jobs),))
            log.info('\tCorrupted    : %d' % (len(corrupt_jobs),))

        # For jobs that have been completed in Sage but the callback failed for some reason, let's send the results to the AGS
        for asset_group_sighting, job_id in fetch_jobs:
            response = current_app.sage.request_passthrough_result(
                'engine.result',
                'get',
                target='default',
                args=job_id,
            )
            if asset_group_sighting.stage != AssetGroupSightingStage.detection:
                asset_group_sighting.set_stage(AssetGroupSightingStage.detection)

            asset_group_sighting.detected(job_id, response)

        active = len(pending_jobs) + len(fetch_jobs)
        return active, seen_jobs

    def sync_jobs_identification(
        self,
        sage_completed_job_guids,
        sage_failed_job_guids,
        sage_pending_job_guids,
        verbose=True,
    ):
        from app.modules.asset_groups.models import Sighting, SightingStage

        sightings = Sighting.query.all()

        start_keys = {'annotation', 'active', 'start', 'matching_set', 'algorithm'}
        end_keys = start_keys | {'json_result', 'end'}

        completed = 0
        fetch_jobs = []
        failed_jobs = []
        pending_jobs = []
        unknown_jobs = []
        corrupt_jobs = []
        seen_jobs = []
        for sighting in tqdm.tqdm(sightings):
            if sighting.jobs:
                for job_id in sighting.jobs:
                    job_metadata = sighting.jobs[job_id]
                    job_data = (sighting, job_id)

                    seen_jobs.append(job_id)

                    if job_metadata.keys() < start_keys:
                        corrupt_jobs.append(job_data)
                    elif job_metadata.get('active'):
                        if job_id in sage_completed_job_guids:
                            fetch_jobs.append(job_data)
                        elif job_id in sage_failed_job_guids:
                            failed_jobs.append(job_data)
                        elif job_id in sage_pending_job_guids:
                            pending_jobs.append(job_data)
                        else:
                            unknown_jobs.append(job_data)
                    else:
                        if job_metadata.keys() < end_keys:
                            if job_id in sage_completed_job_guids:
                                fetch_jobs.append(job_data)
                            elif job_id in sage_failed_job_guids:
                                corrupt_jobs.append(job_data)
                            elif job_id in sage_pending_job_guids:
                                corrupt_jobs.append(job_data)
                            else:
                                corrupt_jobs.append(job_data)
                        else:
                            completed += 1

        if verbose:
            log.info('Identification Jobs')
            log.info('\tCompleted    : %d' % (completed,))
            log.info('\tFailed       : %d' % (len(failed_jobs),))
            log.info('\tActive       : %d' % (len(pending_jobs),))
            log.info('\tFetch Results: %d' % (len(fetch_jobs),))
            log.info('\tMissing      : %d' % (len(unknown_jobs),))
            log.info('\tCorrupted    : %d' % (len(corrupt_jobs),))

        # For jobs that have been completed in Sage but the callback failed for some reason, let's send the results to the AGS
        for sighting, job_id in fetch_jobs:
            response = current_app.sage.request_passthrough_result(
                'engine.result',
                'get',
                target='default',
                args=job_id,
            )
            if sighting.stage != SightingStage.identification:
                sighting.set_stage(SightingStage.identification)

            sighting.identified(job_id, response)

        active = len(pending_jobs) + len(fetch_jobs)
        return active, seen_jobs

    def get_status(self):
        if is_module_enabled('codex_annotations'):
            from app.modules.codex_annotations.models import CodexAnnotation as Annotation
        elif is_module_enabled('scout_annotations'):
            from app.modules.scout_annotations.models import ScoutAnnotation as Annotation
        from app.modules.assets.models import Asset

        # Get Sage data
        sage_assets = current_app.sage.request_passthrough_result(
            'asset.list', 'get', target='sync'
        )
        sage_annots = current_app.sage.request_passthrough_result(
            'annotation.list', 'get', target='sync'
        )
        engine = current_app.sage.request_passthrough_result(
            'engine.status', 'get', target='default'
        )
        jobs = current_app.sage.request_passthrough_result(
            'engine.list', 'get', target='default'
        )['json_result']
        engine_sync = current_app.sage.request_passthrough_result(
            'engine.status', 'get', target='sync'
        )
        jobs_sync = current_app.sage.request_passthrough_result(
            'engine.list', 'get', target='sync'
        )['json_result']

        # Get Houston data
        houston_assets = Asset.query.with_entities(Asset.guid).all()
        houston_annots = Annotation.query.with_entities(Annotation.guid).all()

        sage_compatible_mime_types = current_app.config.get(
            'SAGE_MIME_TYPE_WHITELIST_EXTENSIONS', []
        )
        houston_compatible_assets = (
            Asset.query.filter(Asset.mime_type.in_(sage_compatible_mime_types))
            .with_entities(Asset.guid)
            .all()
        )

        houston_sage_assets = Asset.query.with_entities(Asset.content_guid).all()
        houston_sage_annots = Annotation.query.with_entities(
            Annotation.content_guid
        ).all()

        # Standardize
        sage_assets = {from_sage_uuid(guid) for guid in sage_assets}
        sage_annots = {from_sage_uuid(guid) for guid in sage_annots}

        houston_assets = {guid for (guid,) in houston_assets if guid is not None}
        houston_compatible_assets = {
            guid for (guid,) in houston_compatible_assets if guid is not None
        }
        houston_annots = {guid for (guid,) in houston_annots if guid is not None}

        houston_incompatible_assets = houston_assets - houston_compatible_assets
        houston_incompatible_annots = (
            Annotation.query.filter(
                Annotation.asset_guid.in_(houston_incompatible_assets)
            )
            .with_entities(Annotation.guid)
            .all()
        )
        houston_incompatible_annots = {
            guid for (guid,) in houston_incompatible_annots if guid is not None
        }

        houston_sage_assets_none = sum(guid is None for (guid,) in houston_sage_assets)
        houston_sage_annots_none = sum(guid is None for (guid,) in houston_sage_annots)

        houston_sage_assets = {
            guid for (guid,) in houston_sage_assets if guid is not None
        }
        houston_sage_annots = {
            guid for (guid,) in houston_sage_annots if guid is not None
        }

        houston_sage_assets = houston_sage_assets - houston_incompatible_assets
        houston_sage_annots = houston_sage_annots - houston_incompatible_annots

        log.info('Assets')
        log.info(
            '\tHouston       : %d (out of %d, %d Nones, %d Incompatible)'
            % (
                len(houston_sage_assets),
                len(houston_assets),
                houston_sage_assets_none,
                len(houston_incompatible_assets),
            )
        )
        log.info('\tSage          : %d' % (len(sage_assets),))
        log.info('\tSage - Houston: %d' % (len(sage_assets - houston_sage_assets),))
        log.info('\tHouston - Sage: %d' % (len(houston_sage_assets - sage_assets),))
        log.info('\tHouston ^ Sage: %d' % (len(houston_sage_assets ^ sage_assets),))
        log.info('\tHouston | Sage: %d' % (len(houston_sage_assets | sage_assets),))
        log.info('\tHouston & Sage: %d' % (len(houston_sage_assets & sage_assets),))
        log.info('')
        log.info('Annotations')
        log.info(
            '\tHouston       : %d (out of %d, %d Nones, %d Incompatible)'
            % (
                len(houston_sage_annots),
                len(houston_annots),
                houston_sage_annots_none,
                len(houston_incompatible_annots),
            )
        )
        log.info('\tSage          : %d' % (len(sage_annots),))
        log.info('\tSage - Houston: %d' % (len(sage_annots - houston_sage_annots),))
        log.info('\tHouston - Sage: %d' % (len(houston_sage_annots - sage_annots),))
        log.info('\tHouston ^ Sage: %d' % (len(houston_sage_annots ^ sage_annots),))
        log.info('\tHouston | Sage: %d' % (len(houston_sage_annots | sage_annots),))
        log.info('\tHouston & Sage: %d' % (len(houston_sage_annots & sage_annots),))

        log.info('Job Engine Workers')
        for item, online in sorted(engine.items()):
            log.info(
                '\t%s: %s'
                % (
                    item.ljust(14),
                    'Up' if online else 'Offline',
                )
            )

        log.info('Sync Job Engine Workers')
        for item, online in sorted(engine_sync.items()):
            log.info(
                '\t%s: %s'
                % (
                    item.ljust(14),
                    'Up' if online else 'Offline',
                )
            )

        statuses, sage_jobs = self.get_job_status(jobs)
        log.info('Jobs Status')
        for item, total in sorted(statuses.items()):
            log.info(
                '\t%s: %d'
                % (
                    str(item).ljust(14),
                    total,
                )
            )

        # log.info('Jobs (%d)' % (len(sage_jobs),))
        # for job_id, status in sage_jobs:
        #     log.info(
        #         '\t%s: %s'
        #         % (
        #             job_id.ljust(14),
        #             status,
        #         )
        #     )

        statuses, sage_jobs = self.get_job_status(jobs_sync)
        log.info('Sync Jobs Status')
        for item, total in sorted(statuses.items()):
            log.info(
                '\t%s: %d'
                % (
                    str(item).ljust(14),
                    total,
                )
            )

        # log.info('Sync Jobs (%d)' % (len(sage_jobs),))
        # for job_id, status in sage_jobs:
        #     log.info(
        #         '\t%s: %s'
        #         % (
        #             job_id.ljust(14),
        #             status,
        #         )
        #     )


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    app.sage = SageManager()
    from app.extensions.api import api_v1

    """
    Init Passthroughs module.
    """
    api_v1.add_oauth_scope('sage:read', 'Provide access to Sage API')
    api_v1.add_oauth_scope('sage:write', 'Provide write access to Sage API')

    # Touch underlying modules
    from . import resources  # NOQA

    api_v1.add_namespace(resources.sage)
