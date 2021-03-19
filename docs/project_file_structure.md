# Project File Structure

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
