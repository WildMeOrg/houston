# -*- coding: utf-8 -*-
import logging

from app.extensions.celery import celery

# from app.extensions.intelligent_agent import IntelligentAgent

log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def intelligent_agent_setup_periodic_tasks(sender, **kwargs):
    from app.extensions.intelligent_agent.models import TwitterBot

    seconds = TwitterBot.get_periodic_interval()
    log.warning(
        f'>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> SETUP_PERIODIC {sender} (sec={seconds})'
    )
    sender.add_periodic_task(
        10,
        twitterbot_collect.s(),
    )


@celery.task
def twitterbot_collect():
    from app.extensions.intelligent_agent.models import TwitterBot

    if not TwitterBot.is_enabled():
        # TODO this arguably should *remove* the period task
        # also (related) we need to figure out how to stop/restart/reset periodic task if/when interval changes
        log.info('TwitterBot disabled; skipping periodic task')
        return
    try:
        tb = TwitterBot()
        tb.collect()
    except Exception as ex:
        log.warning(f'twitterbot_collect() failed: {str(ex)}')
