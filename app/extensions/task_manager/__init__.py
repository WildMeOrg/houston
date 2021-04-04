# -*- coding: utf-8 -*-
# pylint: disable=no-self-use
"""
Task manager.

"""

from flask import current_app, request, session, render_template  # NOQA
from flask_login import current_user  # NOQA
import logging
import pytz
import types
from celery import Celery
log = logging.getLogger(__name__)

# only allow periodicity up to 24hrs
MAX_PERIOD = (24*60)

# TODO, broker endpoint(maybe) and port (definitely) need to be config param
celeryTask = Celery(__name__, broker='redis://localhost:6379/0')

class TaskManager(object):
    # pylint: disable=abstract-method
    """
    Manager for handling asynchronous task processing. Currently implemented using Celery
    """
    __instance = None
    @staticmethod
    def getInstance():
        """ Static access method. """
        if TaskManager.__instance is None:
            TaskManager()
        return TaskManager.__instance

    def __init__(self):
        if TaskManager.__instance is not None:
            raise Exception("TaskManager is a singleton!")
        else:
            TaskManager.__instance = self
        # pylint: disable=unused-argument
        # Create periodic background checking of stuff, one minute chosen as arbitrary value
        celeryTask.conf.beat_schedule = {
            'one-minute-periodic': {
                'task': "task_manager.one_minute_periodic",
                'schedule': 60
            }
        }
        timezone = current_app.config.get('TIMEZONE')
        celeryTask.conf.timezone = timezone
        celeryTask.conf.enable_utc = timezone == pytz.timezone('UTC')

        # Two dimensional, first dimension is dictionary of period,
        # second is the list of callback methods registered
        self.minute_callbacks = {}
        self.minute_counter = 0

    @classmethod
    def register_callback(cls, period, method):
        TaskManager.getInstance().register_callback_method(period, method)

    def register_callback_method(self, period, method):
        assert(isinstance(period, int))
        assert(period <= MAX_PERIOD)
        assert(isinstance(method, (types.MethodType,)))

        if period in self.minute_callbacks.keys():
            self.minute_callbacks[period].append(method)
        else:
            self.minute_callbacks[period] = [method]


@celeryTask.task()
def one_minute_periodic(self):

    log.warning("doing periodic stuff")
    # Feels slightly clunky, is there a better way to do this?
    self.minute_counter += 1
    for period in self.minute_callbacks.keys():
        if self.minute_counter % period == 0:
            for callback in self.minute_callbacks[period]:
                callback()

    if self.minute_counter == MAX_PERIOD:
        self.minute_counter = 0
