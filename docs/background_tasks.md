# Background and Periodic Tasks using Celery

## Flask Celery documentation

Flask has a page on Celery with a very simple example but it does not
really fit with the way our application is structured.

[https://flask.palletsprojects.com/en/1.1.x/patterns/celery/?highlight=celery](https://flask.palletsprojects.com/en/1.1.x/patterns/celery/?highlight=celery)

## Define a Celery Task

For example to define a task `check_some_stuff` in
`app/extensions/example_celery_tasks/tasks.py`:

```
# -*- coding: utf-8 -*-
from flask import current_app
import requests

from app.extensions.celery import celery


@celery.task()
def check_some_stuff(*args, **kwargs):
    some_url = current_app.config.get('SOME_URL')
    resp = requests.get(some_url)
    # Do something with the response
```

Register it in `app/extensions/celery.py` under `# register celery tasks`:

```
# register celery tasks
from app.extensions.example_celery_tasks import tasks  # noqa
```

## Background Tasks

For example, when an API is called and we need to do some background
jobs that take some time, we can let celery add this task to the queue
and execute it in the background.

Example view code:

```
@blueprint.route('/call')
def call(*args, **kwargs):
    from .tasks import check_some_stuff

    result = check_some_stuff.delay('api called')
    # Store result id in database
    response = make_response(repr(result), 200)
    response.mimetype = 'text/plain'
    return response
```

Add the celery task `check_some_stuff` to the queue by doing:

```
result = check_some_stuff.delay('api called')
```

`result` is something like
`<AsyncResult: c965fc97-ed63-44a6-86b3-bfd6656f72b2>`.  This contains an
id that we can use to look up the status of the background job.

To look up the status of a background job, you might do something like:

```
@blueprint.route('/result/<string:task_id>')
def get_result(task_id, *args, **kwargs):
    from .tasks import check_some_stuff

    result = check_some_stuff.AsyncResult(task_id)
    body = f'state={result.state} result={result.result}'
    response = make_response(body, 200)
    response.mimetype = 'text/plain'
    return response
```

You need to run a celery worker to process the queue:

```
docker-compose exec houston celery -A app.extensions.celery.celery worker
```

## Periodic Tasks

To run the task `check_some_stuff` every 10 seconds,
in `app/extensions/example_celery_tasks/tasks.py`:

```
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(10.0, check_some_stuff.s('hello'), name='add every 10')
```

To run the celery periodic task, you need a celery worker and celery
beat.  You can run both in one command:

```
docker-compose exec houston celery -A app.extensions.celery.celery worker -B -l DEBUG
```

or run worker and beat as 2 commands:

```
docker-compose exec houston celery -A app.extensions.celery.celery worker
```

and

```
docker-compose exec houston celery -A app.extensions.celery.celery beat -l DEBUG
```

## Check Results

You should be able to look at the results on redis using python:

```
root@0d5a2e7075f3:/code# python
Python 3.9.1 (default, Feb  9 2021, 07:42:03)
[GCC 8.3.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import redis
>>> r = redis.Redis('redis')
>>> r.keys()
[b'celery-task-meta-fe9f21d5-1fa6-4789-bcf1-3caadfd2d2c6', b'celery-task-meta-9f3b3fdf-e1bb-4cd8-bbbf-f6667d239401', b'_kombu.binding.celery']
>>> r.get(r.keys()[0])
b'{"status": "SUCCESS", "result": null, "traceback": null, "children": [], "date_done": "2021-04-06T00:48:21.560784", "task_id": "fe9f21d5-1fa6-4789-bcf1-3caadfd2d2c6"}'
```

## Known issues

Tried using postgresql as the result backend but our sqlalchemy utils is
too old (probably):

```
Traceback (most recent call last):
  File "/usr/local/lib/python3.9/site-packages/celery/app/trace.py", line 536, in trace_task
    return task.__trace__(uuid, args, kwargs, request)
  File "/usr/local/lib/python3.9/site-packages/celery/app/trace.py", line 524, in trace_task
    I, _, _, _ = on_error(task_request, exc, uuid)
  File "/usr/local/lib/python3.9/site-packages/celery/app/trace.py", line 358, in on_error
    R = I.handle_error_state(
  File "/usr/local/lib/python3.9/site-packages/celery/app/trace.py", line 165, in handle_error_state
    return {
  File "/usr/local/lib/python3.9/site-packages/celery/app/trace.py", line 212, in handle_failure
    task.backend.mark_as_failure(
  File "/usr/local/lib/python3.9/site-packages/celery/backends/base.py", line 164, in mark_as_failure
    self.store_result(task_id, exc, state,
  File "/usr/local/lib/python3.9/site-packages/celery/backends/base.py", line 434, in store_result
    self._store_result(task_id, result, state, traceback,
  File "/usr/local/lib/python3.9/site-packages/celery/backends/database/__init__.py", line 47, in _inner
    return fun(*args, **kwargs)
  File "/usr/local/lib/python3.9/site-packages/celery/backends/database/__init__.py", line 120, in _store_result
    task = self.task_cls(task_id)
  File "<string>", line 4, in __init__
  File "/usr/local/lib/python3.9/site-packages/sqlalchemy/orm/state.py", line 427, in _initialize_instance
    manager.dispatch.init(self, args, kwargs)
  File "/usr/local/lib/python3.9/site-packages/sqlalchemy/event/attr.py", line 320, in __call__
    fn(*args, **kw)
  File "/usr/local/lib/python3.9/site-packages/sqlalchemy/orm/events.py", line 226, in wrap
    return fn(target, *arg, **kw)
  File "/usr/local/lib/python3.9/site-packages/sqlalchemy_utils/listeners.py", line 27, in instant_defaults_listener
    if callable(column.default.arg):
AttributeError: 'Sequence' object has no attribute 'arg'
```
