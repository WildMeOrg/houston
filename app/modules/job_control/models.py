# -*- coding: utf-8 -*-
"""Provides UI space served directly from this application"""
import logging

from app.modules.asset_groups.models import AssetGroupSighting
from app.modules.sightings.models import Sighting


log = logging.getLogger(__name__)


# Jobs are only supported on specific classes at the moment
class JobControl(object):

    # Called by a periodic background task,
    @classmethod
    def check_jobs(cls):
        AssetGroupSighting.check_jobs()
        Sighting.check_jobs()

    # Central point for all "job" related things to be accessed.
    @classmethod
    def print_jobs(cls):
        AssetGroupSighting.print_jobs()
        Sighting.print_jobs()
