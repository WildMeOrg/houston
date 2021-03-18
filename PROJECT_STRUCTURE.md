# Project Structure

## Root folder

Folders:

* `app` - This RESTful API Server example implementation is here.
* `flask_restx_patched` - There are some patches for Flask-RESTX (read
  more in *Patched Dependencies* section).
* `migrations` - Database migrations are stored here (see `invoke --list` to
  learn available commands, and learn more about PyInvoke usage below).
* `tasks` - [PyInvoke](http://www.pyinvoke.org/) commands are implemented here.
* `tests` - These are [pytest](http://pytest.org) tests for this RESTful API
  Server example implementation.
* `docs` - It contains just images for the README, so you can safely ignore it.
* `deploy` - It contains some application stack examples.

Files:

* `README.md`
* `config.py` - This is a config file of this RESTful API Server example.
* `conftest.py` - A top-most pytest config file (it is empty, but it [helps to
  have a proper PYTHON PATH](http://stackoverflow.com/a/20972950/1178806)).
* `.coveragerc` - [Coverage.py](http://coverage.readthedocs.org/) (code
  coverage) config for code coverage reports.
* `.travis.yml` - [Travis CI](https://travis-ci.org/) (automated continuous
  integration) config for automated testing.
* `.pylintrc` - [Pylint](https://www.pylint.org/) config for code quality
  checking.
* `Dockerfile` - Docker config file which is used to build a Docker image
  running this RESTful API Server example.
* `.dockerignore` - Lists files and file masks of the files which should be
  ignored while Docker build process.
* `.gitignore` - Lists files and file masks of the files which should not be
  added to git repository.
* `LICENSE` - MIT License, i.e. you are free to do whatever is needed with the
  given code with no limits.

## Application Structure

```
app/
├── requirements.txt
├── __init__.py
├── extensions
│   └── __init__.py
└── modules
    ├── __init__.py
    ├── api
    │   └── __init__.py
    ├── auth
    │   ├── __init__.py
    │   ├── models.py
    │   ├── parameters.py
    │   └── views.py
    ├── users
    │   ├── __init__.py
    │   ├── models.py
    │   ├── parameters.py
    │   ├── permissions.py
    │   ├── resources.py
    │   └── schemas.py
    └── teams
        ├── __init__.py
        ├── models.py
        ├── parameters.py
        ├── resources.py
        └── schemas.py
```

* `app/requirements.txt` - The list of Python (PyPi) requirements.
* `app/__init__.py` - The entrypoint to this RESTful API Server example
  application (Flask application is created here).
* `app/extensions` - All extensions (e.g. SQLAlchemy, OAuth2) are initialized
  here and can be used in the application by importing as, for example,
  `from app.extensions import db`.
* `app/modules` - All endpoints are expected to be implemented here in logicaly
  separated modules. It is up to you how to draw the line to separate concerns
  (e.g. you can implement a monolith `blog` module, or split it into
  `topics`+`comments` modules).

## Module Structure

Once you added a module name into `config.ENABLED_MODULES`, it is required to
have `your_module.init_app(app, **kwargs)` function. Everything else is
completely optional. Thus, here is the required minimum:

```
your_module/
└── __init__.py
```

, where `__init__.py` will look like this:

```python
def init_app(app, **kwargs):
    pass
```

In this example, however, `init_app` imports `resources` and registeres `api`
(an instance of (patched) `flask_restx.Namespace`). Learn more about the
"big picture" in the next section.


## Where to start reading the code?


The easiest way to start the application is by using PyInvoke command `app.run`
implemented in [`tasks/app/run.py`](tasks/app/run.py):

```
$ invoke app.run
```

The command creates an application by running
[`app/__init__.py:create_app()`](app/__init__.py) function, which in its turn:

1. loads an application config;
2. initializes extensions:
   [`app/extensions/__init__.py:init_app()`](app/extensions/__init__.py);
3. initializes modules:
   [`app/modules/__init__.py:init_app()`](app/modules/__init__.py).

Modules initialization calls `init_app()` in every enabled module
(listed in `config.ENABLED_MODULES`).

Let's take `teams` module as an example to look further.
[`app/modules/teams/__init__.py:init_app()`](app/modules/teams/__init__.py)
imports and registers `api` instance of (patched) `flask_restx.Namespace`
from `.resources`. Flask-RESTX `Namespace` is designed to provide similar
functionality as Flask `Blueprint`.

[`api.route()`](app/modules/teams/resources.py) is used to bind a
resource (classes inherited from `flask_restx.Resource`) to a specific
route.

Lastly, every `Resource` should have methods which are lowercased HTTP method
names (i.e. `.get()`, `.post()`, etc). This is where users' requests end up.
