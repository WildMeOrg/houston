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
        if is_module_enabled('asset_groups'):
            from app.modules.asset_groups.models import AssetGroupSighting

            AssetGroupSighting.check_jobs()

        if is_module_enabled('sightings'):
            from app.modules.sightings.models import Sighting

            Sighting.check_jobs()

        if is_module_enabled('missions'):
            from app.modules.missions.models import Mission

            Mission.check_jobs()

    # Central point for all "job" related things to be accessed.
    @classmethod
    def print_jobs(cls):
        if is_module_enabled('asset_groups'):
            from app.modules.asset_groups.models import AssetGroupSighting

            AssetGroupSighting.print_jobs()

        if is_module_enabled('sightings'):
            from app.modules.sightings.models import Sighting

            Sighting.print_jobs()

        if is_module_enabled('missions'):
            from app.modules.missions.models import Mission

            Mission.check_jobs()
