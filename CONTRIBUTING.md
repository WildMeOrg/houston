# Contributing to Houston

All contributions are welcome and encouraged. There are a few guidelines and styling aspects that we require and encourage you to use so that we might see this project through many years of successful development.

## Development Guidelines

### Pull Request Checklist

To submit a pull request (PR) to Houston, we require the following standards to be enforced.  Details on how to configure and pass each of these required checks is detailed in the sections in this guideline section.

* **Ensure that the PR is properly formatted**
  * We require code formatting with Brunette (a *better* version of Black) and linted with Flake8 using the pre-commit (includes automatic checks with brunette and flake8 plus includes other general line-ending, single-quote strings, permissions, and security checks)
  ```
  # Command Line Example
  pre-commit run --all-files
  ```
* **Ensure that the PR is properly rebased**
  * We require new feature code to be rebased onto the latest version of the `develop` branch.
  ```
  git fetch -p
  git checkout <feature-branch>
  git diff origin/<feature-branch>..  # Check there's no difference between local branch and remote branch
  git rebase -i origin/develop  # "Pick" all commits in feature branch
  # Resolve all conflicts
  git log --graph --oneline --decorate origin/develop HEAD  # feature-branch commits should be on top of origin/develop
  git show --reverse origin/develop..  # Check the changes in each commit if necessary
  git push --force origin <feature-branch>
  ```
* **Ensure that the PR uses a consolidated database migration**
  * We require new any database migrations (optional) with Alembic are consolidated and condensed into a single file and version.  Exceptions to this rule (allowing possibly up to 3) will be allowed after extensive discussion and justification.
  * All database migrations should be created using a downgrade revision that matches the existing revision used on the `develop` branch.  Further,a PR should never be merged into develop that contains multiple revision heads.
  ```
  invoke app.db.downgrade <develop branch revision ID>
  rm -rf migrations/versions/<new migrations>.py
  invoke app.db.migrate
  invoke app.db.upgrade
  invoke app.db.history  # Check that the history matches
  invoke app.db.heads  # Ensure that there is only one head
  ```
* **Ensure that the PR is properly tested**
  * We require new feature code to be tested via Python tests and simulated REST API tests.  We use PyTest  to ensure that your code is working cohesively and that any new functionality is exercised.
  * We require new feature code to also be fully compatible with a containerized runtime environment like Docker.
  ```
  pytest
  ```
* **Ensure that the PR is properly covered**
  * We require new feature code to be tested (previous item) and that the percentage of the code covered by tests does not decrease.  We use PyTest Coverage and CodeCov.io to ensure that your code is being properly covered by new tests.
  * To export a HTML report of the current coverage statistics, run the following:
  ```
  pytest -s -v --cov=./ --cov-report=html
  open _coverage/html/index.html
  ```
* **Ensure that the PR is properly sanitized**
  * We require the PR to not include large files (images, database files, etc) without using [GitHub Large File Store (LFS)](https://git-lfs.github.com).
  ```
  git lfs install
  git lfs track "*.png"
  git add .gitattributes
  git add image.png
  git commit -m "Add new image file"
  git push
  ```
  * We also require any sensitive code, configurations, or pre-specified values be omitted, truncated, or redacted.  For example, the file `_db/secrets/py` is not committed into the repository and is ignored by `.gitignore`.
* **Ensure that the PR is properly reviewed**
  * After the preceding checks are satisfied, the code is ready for review.  All PRs are required to be reviewed and approved by at least one registered contributor or administrator on the Houston project.
  * When the PR is created in GitHub, make sure that the repository is specified as `WildMeOrg/houston` and not its original fork.  Further, make sure that the base branch is specified as `develop` and not `master`.


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

### PyInvoke Installation
Several `invoke` commands are referenced in this doc. These are helpful tools using the PyInvoke library, which must
be installed on your local machine. Install it following instructions in the [PyInvoke docs.](https://docs.pyinvoke.org/en/stable//)

Be sure to list other invoke commands with `invoke -l` and inspect them.
There are many useful tools here that can save you time.

#### To add Invoke bash-completion
```
export SCRIPT="$(pwd)/.invoke-completion.sh"
invoke --print-completion-script bash > $SCRIPT
echo "source $SCRIPT" >> virtualenv/houston3.7/bin/activate
```
### Virtual Environment
If you are running Houston outside the docker-compose setup for any reason you will need to set up a virtual environment.
Most `invoke` commands assume that you are using the virtual environment provided, and you should activate it if you plan
to use them outside the Houston the docker container.

```
#initial setup
bash
./scripts/venv.sh

#activation whenever developing or in a new terminal
source virtualenv/houston3.7/bin/activate

```

### Install Dependencies

For locally running Houston. Can be skipped if you develop entirely inside the docker-compose containers.

```bash
invoke dependencies.install
```

### Running Docker Containers

When `docker-compose up` is run from the `deploy/codex/` directory, several Docker containers are started. These are the connected components of the Codex application.

You can view them by using the command `docker-compose ps` in the `deploy/codex/` directory and see something like this:

```
        Name                      Command                       State                          Ports
-------------------------------------------------------------------------------------------------------------------
codex_acm_1            /docker-entrypoint.sh wait ...   Up                      0.0.0.0:82->5000/tcp
codex_db_1             docker-entrypoint.sh postgres    Up                      5432/tcp
codex_dev-frontend_1   /docker-entrypoint.sh            Up
codex_edm_1            /usr/local/tomcat/bin/cata ...   Up                      0.0.0.0:81->8080/tcp
codex_gitlab_1         /assets/wrapper                  Up (health: starting)   22/tcp, 443/tcp, 0.0.0.0:85->80/tcp
codex_houston_1        /docker-entrypoint.sh wait ...   Up                      0.0.0.0:83->5000/tcp
codex_redis_1          docker-entrypoint.sh redis ...   Up                      6379/tcp
codex_www_1            /docker-entrypoint.sh ngin ...   Up                      0.0.0.0:84->80/tcp
```

This describes the container name, status and ports to access. Access can be interpreted thus:

```
    http://localhost:82 to access acm,
    http://localhost:81 to access edm,
    http://localhost:85 to access gitlab,
    http://localhost:83 to access houston,
    http://localhost:84 to access the frontend.
```

These containers are available to enter on the command line using `docker-compose exec [CONTAINER NAME] /bin/bash`. This command will grant you command line access as a root user for
whichever Codex application component you choose. These are defined in the `docker-compose.yml` as different services. You will likely want to connect to `dev-frontend` for the react front end, `houston` for Houston or `edm` for the EDM.

Please refer to the Docker documentation for other common container actions.

Development on Houston or other Codex components should be done by testing new code against the full application in these running docker containers. Running tests or migrations outside the docker-compose environment is an extra tool at your disposal but can be unpredictable and is not considered complete.

### Mounted Directories

#### Houston
The docker-compose arrangement will attempt to mount local directories for development purposes. For Houston, this is the root repository directory.

If you create or modify a file in the local Houston repository you will be able to see the changes reflected when you `docker exec` inside the Houston container, and
changes in the container will be reflected outside much like a symlinked directory.


#### Frontend
The docker-compose.yml file also mounts a `_frontend` directory for the front end application. If you clone the houston repository with the README recommended
`git clone --recurse-submodules https://github.com/WildMeOrg/houston.git` the `_frontend` directory will contain the front end code, but not necessarily the latest.

If you want to rebuild the front end, use the command `invoke dependencies.install-frontend-ui`. This will update the `_frontend` folder in the houston repo. Like houston the files in this folder can be modified, and the changes will be reflected in your running `dev-frontend` container.

If you want to change the mountpoint to a different directory for your locally cloned codex-frontend repository to make changes and commits easier, you can change it
in the `deploy/codex/docker-compose.yml` by altering the `dev-frontend` volume mapping `- ../../_frontend:/code` to a directory outside your Houston repository.

More details about Codex front end contribution are outside the scope of this README but can be found here: [**codex-frontend**](https://github.com/WildMeOrg/codex-frontend)

#### EDM
The EDM is a compiled Java application, and no volume mapping solution to a running Docker container is available at this time.

### Testing

New Houston code must be tested with `pytest`. If dependencies are set up correctly an initial testing run can be done outside the docker container
with the `pytest` command at the root level of the repository.

To fully test you can `docker-compose exec houston /bin/bash` and run `pytest` or
test files inside the container from outside the container in one line using `docker-compose exec houston pytest`.

They can also be run locally with simply `pytest`.

These methods can target a specific app module by altering the command to something like this:

    pytest tests/modules/[MODULE NAME]`

And may also the flags `-s` to print all additional logging or `-x` to stop on the first failed test.

### Rebuilding with Invoke

In the process of contributing you will want to sync up with the latest Houston/Codex code. This can result in a database or Docker orchestration
that is incompatible with the new code. Invoke commands will assist in a clean start.

If there are containers failing, database changes that are not migrating successfully or connections between these containers
that are not being established try rebuilding all containerized Docker resources:
`invoke docker-compose.rebuild`


If there are specifically Gitlab authentication or startup issues, try rebuilding Gitlab:
`invoke docker-compose.rebuild-gitlab`

#### Cleaning up with Docker commands

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
