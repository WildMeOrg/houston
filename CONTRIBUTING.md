# Contributing to Houston

All contributions are welcome and encouraged. There are a few guidelines and styling aspects that we require and encourage you to use so that we might see this project through many years of successful development.

## Pull Request Considerations

Details on how to configure and pass each of these required checks is detailed in the sections in this guideline section.

### Pre-commit
We require code formatting with Brunette (a *better* version of Black) and linted with Flake8 using the pre-commit (includes automatic checks with brunette and flake8 plus includes other general line-ending, single-quote strings, permissions, and security checks). Pre-commit is installed once and then runs automatically.

### Consolidated database migration
Database migrations (optional) with Alembic are consolidated and condensed into a single file and version.  Exceptions to this rule (allowing possibly up to 3) will be allowed after extensive discussion and justification.
All database migrations should be created using a downgrade revision that matches the existing revision used on the `develop` branch.  Further,a PR should never be merged into develop that contains multiple revision heads.
  ```
  invoke app.db.downgrade <develop branch revision ID>
  rm -rf migrations/versions/<new migrations>.py
  invoke app.db.migrate
  invoke app.db.upgrade
  invoke app.db.history  # Check that the history matches
  invoke app.db.heads  # Ensure that there is only one head
  ```

### Testing
Feature code is tested via Python tests and simulated REST API tests.  We use PyTest  to ensure that your code is working cohesively and that any new functionality is exercised.
Feature code to also be fully compatible with a containerized runtime environment like Docker.
  ```
  pytest
  ```
  
### Test coverage
New feature code should have automated tests, and the percentage of the code covered by tests does not decrease with the addition of new features. We use PyTest Coverage and CodeCov.io to ensure that your code is being properly covered by new tests.
To export a HTML report of the current coverage statistics, run the following:
  ```
  pytest -s -v --cov=./ --cov-report=html
  open _coverage/html/index.html
  ```
  
### Large file sanitation
PRs should not include large files (images, database files, etc) without using [GitHub Large File Store (LFS)](https://git-lfs.github.com).
  ```
  git lfs install
  git lfs track "*.png"
  git add .gitattributes
  git add image.png
  git commit -m "Add new image file"
  git push
  ```
Any sensitive code, configurations, or pre-specified values should be omitted, truncated, or redacted.  For example, the file `_db/secrets/py` is not committed into the repository and is ignored by `.gitignore`.

## Code Style

The code is generally in PEP8 compliance, enforced by flake8 via pre-commit.

Our code uses Google-style docstrings. See examples of this in [Example Google Style Python Docstrings](https://www.sphinx-doc.org/en/master/usage/extensions/example_google.html#example-google).

### Pre-commit

It's recommended that you use `pre-commit` to ensure linting procedures are run
on any commit you make. (See also [pre-commit.com](https://pre-commit.com/)

Reference [pre-commit's installation instructions](https://pre-commit.com/#install) for software installation on your OS/platform. After you have the software installed, run ``pre-commit install`` on the command line. Now every time you commit to this project's code base the linter procedures will automatically run over the changed files.  To run pre-commit on files preemtively from the command line use:

```bash
  git add .
  pre-commit run

  # or

  pre-commit run --all-files
```

See `.pre-commit-config.yaml` for a list of configured linters and fixers.

## Development Environment
### Install from source for troubleshooting

Installation of Houston and the other components of Codex from source is intended to facilitate development leveraging the docker-compose environment. Full deployment of Codex outside docker-compose orchestration is not supported, and any changes should not be considered finished until they have been tested in the docker-compose environment.

#### Clone the Project

```bash
git clone --recurse-submodules https://github.com/USERNAME/houston.git
cd houston/
```
#### Setup Codex Environment

It is recommended to use virtualenv or Anaconda/Miniconda to manage Python
dependencies. Please, learn details yourself.
For quickstart purposes the following will set up a virtualenv for you:

```bash
./scripts/codex/venv.sh
source virtualenv/houston3.7/bin/activate

# To add bash-completion
export SCRIPT="$(pwd)/.invoke-completion.sh"
invoke --print-completion-script bash > $SCRIPT
echo "source $SCRIPT" >> virtualenv/houston3.7/bin/activate
```

Set up and install the package:

```bash
invoke dependencies.install
```

#### Run Server

NOTE: All dependencies and database migrations will be automatically handled,
so go ahead and turn the server ON! (Read more details on this in Tips section)

```bash
export HOUSTON_APP_CONTEXT=codex
$ invoke app.run
```

#### Deploy Server

In general, you deploy this app as any other Flask/WSGI application. There are
a few basic deployment strategies documented in the [`./deploy/`](./deploy/)
folder.


### Installing and running on your local system

#### PyInvoke installation

You'll need to install [pyinvoke](pyinvoke.org) in order to complete the installation.
Run `pip install pyinvoke`, which will install the `invoke` commandline tool.

Several `invoke` commands are referenced in this doc. These are helpful tools using the PyInvoke library, which must
be installed on your local machine. Install it following instructions in the [PyInvoke docs.](https://docs.pyinvoke.org/en/stable//)

Be sure to list other invoke commands with `invoke -l` and inspect them.
There are many useful tools here that can save you time.

To add Invoke bash-completion:
```
export SCRIPT="$(pwd)/.invoke-completion.sh"
invoke --print-completion-script bash > $SCRIPT
echo "source $SCRIPT" >> virtualenv/houston3.7/bin/activate
```

#### Setting up the Codex environment

If you are running Houston outside the docker setup, it is recommended that you set up a [python virtual environment](https://docs.python.org/dev/library/venv.html).
Most `invoke` commands assume that you are using the virtual environment provided; and you should activate it in order to use the application's commands.

Initial setup of the virtual environment:
```bash
./scripts/codex/venv.sh
```

Activation whenever developing or in a new terminal:
```bash
source virtualenv/houston3.7/bin/activate
```

#### Install dependencies

To install the application:
```bash
invoke dependencies.install
```

#### Running the application

```bash
invoke codex.run
```

#### Usage
### Usage Tips

Once you have invoke, you can learn all available commands related to this
project from:

```bash
$ invoke --list
```

Learn more about each command with the following syntax:

```bash
$ invoke --help <task>
```

For example:

```bash
$ invoke --help codex.run
Usage: inv[oke] [--core-opts] codex.run [--options] [other tasks here ...]

Docstring:
  Run DDOTS RESTful API Server.

Options:
  -d, --[no-]development
  -h STRING, --host=STRING
  -i, --[no-]install-dependencies
  -p, --port
  -u, --[no-]upgrade-db
```

Use the following command to enter ipython shell (`ipython` must be installed):

```bash
$ invoke app.env.enter
```

`codex.run` and `app.env.enter` tasks automatically prepare all dependencies
(using `pip install`) and migrate database schema to the latest version.

Database schema migration is handled via `app.db.*` tasks group. The most
common migration commands are `app.db.upgrade` (it is automatically run on
`codex.run`), and `app.db.migrate` (creates a new migration).

You can use [`better_exceptions`](https://github.com/Qix-/better-exceptions)
package to enable detailed tracebacks. Just add `better_exceptions` to the
`app/requirements.txt` and `import better_exceptions` in the `app/__init__.py`.

##### Running the applications

Run the deployment locally with docker-compose:

    docker-compose up -d && sleep 5 && docker-compose ps

Note, the composition can take several minutes to successfully come up.
There are a number of operations setting up the services and automating the connections between them.
All re-ups should be relatively fast.

##### Running the applications with gitlab

If you choose to use the gitlab backend for saving assets, you'll need to configure houston with specific gitlab settings. You may choose to not use it, use a remote instance, or a local instance. The following instructions suggest how to connect to a gitlab instance. By default no gitlab instance is present.

Note, for development it is recommended that you only install gitlab if you need to integrate and test portions of the code that that require gitlab. GitLab is resource heavy. Therefore it is wise to use a remote gitlab instance if possible.

###### Without GitLab

By default the composition (i.e. `docker-compose.yml`) does not run a gitlab instance. The `GITLAB_REMOTE_URI` is set to `-`, which indicates to the houston software that it should not try to connect to gitlab.

###### Remote GitLab

If you choose to use a remotely installed gitlab instance you'll need to set the following variables in your `.env` file:

```
GITLAB_PROTO=https
GITLAB_HOST=gitlab.sub.staging.wildme.io
GITLAB_PORT=443
GITLAB_REMOTE_URI=https://gitlab.sub.staging.wildme.io
GIT_PUBLIC_NAME=Houston
GIT_EMAIL=dev@wildme.org
GITLAB_NAMESPACE=TEST
GITLAB_REMOTE_LOGIN_PAT='<paste-personal-access-token-here>'
GIT_SSH_KEY='<paste-contents-of-id_ssh_key-here>'
```

Note, if you are working with a freshly installed instance of GitLab, you may want to supply `GITLAB_ADMIN_PASSWORD` and nullify (aka leave blank) the `GITLAB_REMOTE_LOGIN_PAT` & `GIT_SSH_KEY` environment variables. Using this method will invoke the houston container's setup init scripts to create both the PAT and SSH key, but only when the houston instance is new.


###### Local GitLab

To use a local gitlab, include the `docker-compose.gitlab.yml` file. To do this add `-f docker-compose.gitlab.yml` to your `docker-compose` command. For example, `docker-compose -f docker-compose.yml -f docker-compose.gitlab.yml up -d`. Hint, use `alias docker-compose='docker-compose -f docker-compose.yml -f docker-compose.gitlab.yml'` so that you don't have to type the configuration options for each command.


##### Cleaning up

Cleanup volumes:

    docker volume rm $(docker volume ls -q | grep houston_)

Big red button:

    docker-compose down && docker volume rm $(docker volume ls -q | grep houston_)

Precision nuke example:

    docker-compose stop houston && docker-compose rm -f houston && docker volume rm houston_houston-var

Docker is conservative about cleaning up unused objects. This can cause Docker to run out of disk space or
other problems. If a new build is experiencing errors try using prune commands.

Prune images not used by existing containers:

    docker image prune -a

Remove all stopped containers:

    docker container prune

Remove networks connecting resources used by Docker:

    docker network prune

Remove all volumes:

    docker volume prune

    NOTE: Removing volumes destroys data stored in them. If you have other Docker projects you are working on or need to preserve development data
    refer to the Docker documentation to filter what volumes you prune.

Remove everything except volumes:

    docker system prune

Including volumes:

    docker system prune --volumes

You can bypass the confirmation for these actions by adding a -f flag.

### Rebuilding with Invoke

In the process of contributing you will want to sync up with the latest Houston/Codex code. This can result in a database or Docker orchestration
that is incompatible with the new code. Invoke commands will assist in a clean start.

If there are containers failing, database changes that are not migrating successfully or connections between these containers
that are not being established try rebuilding all containerized Docker resources:
`invoke docker-compose.rebuild`


If there are specifically Gitlab authentication or startup issues, try rebuilding Gitlab:
`invoke docker-compose.rebuild -s gitlab`


#### Mounted Directories

##### Houston
The docker-compose arrangement will attempt to mount local directories for development purposes. For Houston, this is the root repository directory.

If you create or modify a file in the local Houston repository you will be able to see the changes reflected when you `docker exec` inside the Houston container, and
changes in the container will be reflected outside much like a symlinked directory.


##### Frontend
The docker-compose.yml file also mounts a `_frontend` directory for the front end application. If you clone the houston repository with the README recommended
`git clone --recurse-submodules https://github.com/WildMeOrg/houston.git` the `_frontend` directory will contain the front end code, but not necessarily the latest.

If you want to rebuild the front end, use the command `invoke dependencies.install-frontend-ui`. This will update the `_frontend` folder in the houston repo. Like houston the files in this folder can be modified, and the changes will be reflected in your running `dev-frontend` container.

If you want to change the mountpoint to a different directory for your locally cloned codex-frontend repository to make changes and commits easier, you can change it
in the `docker-compose.yml` by altering the `dev-frontend` volume mapping `- _frontend:/code` to a directory outside your Houston repository.

More details about Codex front end contribution are outside the scope of this README but can be found here: [**codex-frontend**](https://github.com/WildMeOrg/codex-frontend)

##### EDM
The EDM is presently maintained for migration of production platforms from Wildbook to Codex. It will be removed when production platforms have all been migrated.

### Testing

New Houston code must be tested with `pytest`. If dependencies are set up correctly an initial testing run can be done outside the docker container
with the `pytest` command at the root level of the repository.

To fully test you can `docker-compose exec houston /bin/bash` and run `pytest` or
test files inside the container from outside the container in one line using `docker-compose exec houston pytest`.

They can also be run locally with simply `pytest`.

These methods can target a specific app module by altering the command to something like this:

    pytest tests/modules/[MODULE NAME]`

And may also the flags `-s` to print all additional logging or `-x` to stop on the first failed test.

#### Running Integration Tests

Integration tests can be run within the houston container or outside.  If you use `--delete-site`, you must run it on the host.

To install the integration requirements:

```
pip install -r integration_tests/requirements.txt
```

You also need to download the chrome driver for selenium [here](https://chromedriver.chromium.org/downloads) or the gecko (firefox) driver [here](https://github.com/mozilla/geckodriver/releases).

To run the tests:

```
pytest -s -c integration_tests/conftest.py integration_tests/
```

**WARNING!! Running the integration tests create real data and users on the site.**

If you want to delete the houston / edm / sage data on your site before the tests, you can do:

```
pytest --delete-site -s -c integration_tests/conftest.py integration_tests/
```

There are some environment variables you can set for the integration tests:

| Variable           | Default value          |                           |
|--------------------|------------------------|---------------------------|
| `CODEX_URL`        | `http://localhost:84/` | The url of the site to test |
| `ADMIN_EMAIL`      | `root@example.org`     | The email of the first admin user |
| `ADMIN_PASSWORD`   | `password`             | The password of the first admin user |
| `ADMIN_NAME`       | `Test admin`           | The name of the first admin user |
| `SITE_NAME`        | `My test site`         | The name of the site |
| `BROWSER`          | `chrome`               | chrome or firefox |
| `BROWSER_HEADLESS` | `true`                 | True for headless, otherwise pops up browser for the tests |

For example if you have set up your admin user using a different email address, you can do:

```
export ADMIN_EMAIL=myname@mydomain.org
```

### Using the python debugger (pdb)

If you want to use the debugger to step through some code, you can add this to the code (new in python 3.7):

```python
breakpoint()
```

or

```python
import pdb; pdb.set_trace()
```

See the debugger commands here: https://docs.python.org/3/library/pdb.html#debugger-commands

If you want to debug the running houston service, you need to change `tasks/codex/run.py`:

```diff
diff --git a/tasks/codex/run.py b/tasks/codex/run.py
index 8f773f77..49155705 100644
--- a/tasks/codex/run.py
+++ b/tasks/codex/run.py
@@ -117,4 +117,4 @@ def run(
             # )
             use_reloader = False

-        return app.run(host=host, port=port, use_reloader=use_reloader)
+        return app.run(host=host, port=port, use_reloader=use_reloader, debug=True)
```

Stop the running houston service and start it in foreground:

```bash
docker-compose stop houston
docker-compose run --rm -p 83:5000 --name=houston houston
```

The debugger doesn't work for celery tasks but you can try to run the task in
the foreground by removing the `.delay()` part.  Or add logs in the celery task
which should show in `docker-compose logs -f celery_worker`.
