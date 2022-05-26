# -*- coding: utf-8 -*-
"""Provides UI space served directly from this application"""
import logging

from app.modules import is_module_enabled

log = logging.getLogger(__name__)


# Jobs are only supported on specific classes at the moment
class JobControl(object):

    # Called by a periodic background task,
    @classmethod
    def check_jobs(cls):
        last_error = None
        if is_module_enabled('asset_groups'):
            try:
                from app.modules.asset_groups.models import AssetGroupSighting

                AssetGroupSighting.check_jobs()
            except Exception as e:
                last_error = e
                log.error('AssetGroupSighting.check_jobs() error')

        if is_module_enabled('sightings'):
            try:
                from app.modules.sightings.models import Sighting

                Sighting.check_jobs()
            except Exception as e:
                last_error = e
                log.error('Sighting.check_jobs() error')

        if last_error:
            raise last_error

    # Central point for all "job" related things to be accessed.
    @classmethod
    def get_jobs(cls, verbose):
        jobs = []
        if is_module_enabled('asset_groups'):
            from app.modules.asset_groups.models import AssetGroupSighting

            jobs.extend(AssetGroupSighting.get_all_jobs_debug(verbose))

        if is_module_enabled('sightings'):
            from app.modules.sightings.models import Sighting

            jobs.extend(Sighting.get_all_jobs_debug(verbose))

        return jobs
