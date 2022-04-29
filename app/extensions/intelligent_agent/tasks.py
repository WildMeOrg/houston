# -*- coding: utf-8 -*-
import logging

from app.extensions.celery import celery
from app.extensions.intelligent_agent import IntelligentAgentException

log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def intelligent_agent_setup_periodic_tasks(sender, **kwargs):
    # from app.extensions.intelligent_agent.models import TwitterBot

    # FIXME upon startup this seems to not be reading this from db and falling back to default
    #   seems related to no app context yet:   https://stackoverflow.com/q/46540664
    #  also, sometimes(???) celery seems to load before tweepy is loaded or something so TwitterBot fails
    #    maybe read directly from utils.get_persisted_value() ???
    # interval_seconds = TwitterBot.get_periodic_interval()
    interval_seconds = 30
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
    autoretry_for=(IntelligentAgentException,),
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
    raise IntelligentAgentException('too soon, delayed for retry')


DETECTION_RETRIES = 100


@celery.task(
    bind=True,
    autoretry_for=(IntelligentAgentException,),
    default_retry_delay=3,
    max_retries=DETECTION_RETRIES,
)
def intelligent_agent_wait_for_detection_results(self, content_guid):
    from app.extensions.intelligent_agent import IntelligentAgentContent
    from app.modules.assets.models import Asset

    iacontent = IntelligentAgentContent.query.get(content_guid)
    assert iacontent, f'could not get guid={str(content_guid)}'
    assets = iacontent.get_assets()
    if not assets:
        log.info(
            f'intelligent_agent_wait_for_detection_results() no assets in {iacontent}; bailing'
        )
        return
    incomplete = len(assets)
    for asset in assets:
        jobs = Asset.get_jobs_for_asset(asset.guid, False)
        log.debug(
            f'[{self.request.retries}/{DETECTION_RETRIES}] wait for detection? {len(jobs) if jobs else 0} jobs for {asset} on {str(iacontent.guid)}'
        )
        if jobs:
            active_job = False
            for j in jobs:
                if j.get('active', False):
                    active_job = True
                    j_id = j.get('job_id')
                    resp_status = j.get('response', {}).get('status')
                    log.info(
                        f'detection job {j_id} still active, status={resp_status} on {asset}'
                    )
            if not active_job:
                incomplete -= 1
                iacontent.detection_complete_on_asset(asset, jobs)
    if incomplete > 0:
        # we actually catch when we have reached the end and bail ourselves,
        #   so we can notify the user detection never came back
        if self.request.retries >= DETECTION_RETRIES:
            iacontent.detection_timed_out()
            return
        # this will cause retry
        raise IntelligentAgentException(f'detection still pending on {incomplete} assets')
    iacontent.detection_complete()


IDENTIFICATION_RETRIES = 100


@celery.task(
    bind=True,
    autoretry_for=(IntelligentAgentException,),
    default_retry_delay=3,
    max_retries=IDENTIFICATION_RETRIES,
)
def intelligent_agent_wait_for_identification_results(self, content_guid):
    from app.extensions.intelligent_agent import IntelligentAgentContent

    iacontent = IntelligentAgentContent.query.get(content_guid)
    assert iacontent, f'could not get guid={str(content_guid)}'
    sighting = iacontent.get_sighting()
    if not sighting:
        log.info(
            f'intelligent_agent_wait_for_identification_results() no sighting in {iacontent}; bailing'
        )
        return
    log.debug(
        f'[{self.request.retries}/{IDENTIFICATION_RETRIES}] wait for identification? {len(sighting.jobs)} jobs for {sighting} on {str(iacontent.guid)}'
    )

    if not sighting.jobs:
        if self.request.retries >= IDENTIFICATION_RETRIES:
            iacontent.identification_timed_out()
            return
        # this will cause retry
        raise IntelligentAgentException(
            f'identification found no jobs on {sighting} for {iacontent}'
        )

    active_job = None
    for job_id in sighting.jobs:
        if sighting.jobs[job_id].get('active', False):
            active_job = sighting.jobs[job_id]
            active_job['job_id'] = job_id
    if active_job:
        log.debug(
            f'intelligent_agent_wait_for_identification_results() found active job on {sighting} for {iacontent}: {active_job}'
        )
        # this will cause retry
        raise IntelligentAgentException(
            f"identification found active job {active_job['job_id']} on {sighting} for {iacontent}"
        )

    log.debug(f'>>>>>>>>>>>>>>>>> fell thru on {iacontent} with jobs: {sighting.jobs}')
    iacontent.identification_complete()
