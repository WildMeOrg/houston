# -*- coding: utf-8 -*-
"""
Application Users management related tasks for Invoke.
"""

from tasks.utils import app_context_task
from datetime import datetime, timedelta


@app_context_task(
    help={
        'before': 'YYYY-MM-DD hh:mm:ss - index when modified before this date',
        'batch-size': 'how many to index each batch',
        'batch-pause': 'seconds to pause between batches',
    }
)
def catchup_index(context, before, batch_size=100, batch_pause=3):
    from app.modules.elasticsearch.tasks import catchup_index_set

    """
    Start indexing historic data before a certain date, in batches.
    """
    # from app.modules.individuals.tasks import execute_merge_request
    # async_res = execute_merge_request.apply_async(args, eta=deadline)
    conf = {
        'before': datetime.fromisoformat(before).strftime('%Y-%m-%d %H:%M:%S'),
        'batch_size': int(batch_size),
        'batch_pause': int(batch_pause),
    }
    catchup_index_set(conf)
    _kickoff()


@app_context_task()
def catchup_index_continue(context):
    from app.modules.elasticsearch.tasks import catchup_index_get

    conf = catchup_index_get()
    if not conf:
        print(
            'No previous settings to continue.  Use app.codex.elasticsearch.catchup-index instead.'
        )
    _kickoff()


@app_context_task()
def catchup_index_cancel(context):
    from app.modules.elasticsearch.tasks import catchup_index_reset

    catchup_index_reset()
    print(
        'Reset catchup-index configuration.  If running, will stop after current batch.'
    )
    return


def _kickoff():
    from app.modules.elasticsearch.tasks import catchup_index_start

    start_pause = 10
    start_time = datetime.utcnow() + timedelta(seconds=start_pause)
    async_res = catchup_index_start.apply_async(eta=start_time)
    print(
        f'Starting background catchup-indexing in {start_pause} seconds  [{async_res}].'
    )
