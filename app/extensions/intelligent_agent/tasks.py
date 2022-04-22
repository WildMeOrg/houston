# -*- coding: utf-8 -*-
import logging

from app.extensions.celery import celery

# from app.extensions.intelligent_agent import IntelligentAgent

log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def intelligent_agent_setup_periodic_tasks(sender, **kwargs):
    from app.extensions.intelligent_agent.models import TwitterBot

    # FIXME upon startup this seems to not be reading this from db and falling back to default
    #   seems related to no app context yet:   https://stackoverflow.com/q/46540664
    interval_seconds = TwitterBot.get_periodic_interval()
    log.debug(
        f'intelligent_agent_setup_periodic_tasks() starting via {sender} with interval_sconds={interval_seconds}'
    )
    sender.add_periodic_task(
        interval_seconds,
        twitterbot_collect.s(),
    )


@celery.task
def twitterbot_collect():
    from app.extensions.intelligent_agent.models import TwitterBot

    if not TwitterBot.is_enabled():
        # TODO this arguably should *remove* the period task
        # also (related) we need to figure out how to stop/restart/reset periodic task if/when interval changes
        # there seems to be some bugs/problems with alterting beat/periodic tasks.  :(
        #    https://github.com/celery/django-celery-beat/issues/126
        log.info('TwitterBot disabled; skipping periodic task')
        return
    try:
        tb = TwitterBot()
        tb.collect()
    except Exception as ex:
        log.warning(f'twitterbot_collect() failed: {str(ex)}')


@celery.task(
    autoretry_for=(Exception,),
    # seconds until try to send again (including if throttled)
    #  i _think_ this should never be less than minimum_gap?
    default_retry_delay=3,
    max_retries=None,  # keep trying forever
)
def twitterbot_create_tweet_queued(text, in_reply_to):
    from app.extensions.intelligent_agent.models import TwitterBot
    import time

    if not TwitterBot.is_enabled():
        log.info(
            f'twitterbot_create_tweet_queue(): TwitterBot disabled, bailing on tweet "{text}"'
        )
        return

    # the fastest tweets can go out (seconds)
    minimum_gap = 2.0
    last_created = 0.0
    try:
        last_created = float(TwitterBot.get_persisted_value('create_tweet_queued_last'))
    except (ValueError, TypeError):
        last_created = -1.0
    now = time.time()
    if now - last_created > minimum_gap:
        log.debug(
            f'twitterbot_create_tweet_queue(): sufficient gap ({now}:{last_created}), creating tweet'
        )
        tb = TwitterBot()  # can raise exception
        # slight potential for race condition here of course, but hopefully slim and not catastrophic
        TwitterBot.set_persisted_value('create_tweet_queued_last', str(now))
        tweet = tb.create_tweet_direct(text, in_reply_to)
        log.info(f'twitterbot_create_tweet_queue(): {tweet} created')
        return

    log.info(
        f'twitterbot_create_tweet_queue(): insufficient gap ({now}:{last_created}), holding tweet for retry [{text}]'
    )
    raise Exception('too soon, delayed for retry')
