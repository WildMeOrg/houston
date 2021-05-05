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

### Running Docker Containers

When `docker-compose up` is run from the `deploy/codex/` directory, several Docker containers are started. These are the connected components of the Codex application.

You can view them by using the command `docker ps -a` and see something like this: 

```
CONTAINER ID   IMAGE                          COMMAND                  CREATED             STATUS                       PORTS                                 NAMES
e3939c800021   codex_houston                  "/docker-entrypoint.…"   About an hour ago   Up About an hour             0.0.0.0:83->5000/tcp                  codex_houston_1
5c0b2ab64bdc   dpage/pgadmin4                 "/entrypoint.sh"         22 hours ago        Up About an hour             443/tcp, 0.0.0.0:8000->80/tcp         codex_pgadmin_1
4761da5d9168   redis:latest                   "docker-entrypoint.s…"   22 hours ago        Up About an hour             6379/tcp                              codex_redis_1
9560f26f0227   wildme/edm:latest              "/usr/local/tomcat/b…"   22 hours ago        Up About an hour             0.0.0.0:81->8080/tcp                  codex_edm_1
566e59074f42   nginx:latest                   "/docker-entrypoint.…"   22 hours ago        Up About an hour             0.0.0.0:84->80/tcp                    codex_www_1
7925cbde4337   wildme/wildbook-ia:nightly     "/docker-entrypoint.…"   22 hours ago        Up About an hour             0.0.0.0:82->5000/tcp                  codex_wbia_1
77624c19e02d   postgres:10                    "docker-entrypoint.s…"   22 hours ago        Up About an hour             5432/tcp                              codex_db_1
ba8962d4cf8e   gitlab/gitlab-ce:13.9.3-ce.0   "/assets/wrapper"        22 hours ago        Up About an hour (healthy)   22/tcp, 443/tcp, 0.0.0.0:85->80/tcp   codex_gitlab_1
f259ede38b22   node:latest                    "/docker-entrypoint.…"   22 hours ago        Up About an hour                                                   codex_dev-frontend_1
```

These containers are available to enter on the command line using `docker exec -it [CONTAINER NAME] \bin\bash`. This command will grant you command line access as a root user for 
whichever Codex application component you choose; `codex_dev-frontend_1` for the react front end, `codex_houston_1` for Houston or `codex_edm_1` for the EDM.

Please refer to the Docker documentation for other common container actions.

Development on Houston or other Codex components should be done by testing new code against the full application in these running docker containers. Running tests or migrations outside the docker-compose environment is an extra tool at your disposal but can be unpredictable and is not considered complete.

### Mounted Directories

#### Houston
The docker-compose arrangement will attempt to mount local directories for development purposes. For Houston, this is the root repository directory. 

If you create or modify a file in the local Houston repository you will be able to see the changes reflected when you `docker exec` inside the Houston container.

This does not go the other way. Changes made inside the container reside only there.

#### Frontend
The docker-compose.yml file also mounts a `_frontend` directory for the front end application. Since we do not build the front end locally by default, this does not map to any location.
If you want to build the front end, use the command `invoke dependencies.install-frontend-ui`. This will create a `_frontend` folder in the houston repo that contains files which 
can be modified, and the changes will be reflected in your running `codex_dev-frontend` container.

If you want to change the mountpoint to a different directory for your locally cloned Codex frontend repository to make changes and commits easier, you can change it
in the `deploy/codex/docker-compose.yml` by altering the `dev-frontent` volume mapping `- ../../_frontend:/code` to a directory outside your Houston repository.

More details about Codex front end contribution are outside the scope of this README but can be found here: [**codex-frontend**](https://github.com/WildMeOrg/codex-frontend)

#### EDM
The EDM is a compiled Java application, and no volume mapping solution to a running Docker container is available at this time. 

### Testing

New Houston code must be tested with `pytest`. If dependencies are set up correctly an initial testing run can be done outside the docker container 
with the `pytest` command at the root level of the repository.

To fully test, `docker exec` into the Houston container and run tests there by setting `FLASK_CONFIG= pytest -s -x` on the command line. 

Both of these methods can target a specific app module by altering the command to something like this:

`pytest tests/modules/[MODULE NAME]` or `FLASK_CONFIG= pytest tests/modules/[MODULE NAME] -s -x`

### Migrations

If your modifications creates a database migration, the `invoke` tasks to perform the migration must be tested inside the Houston docker container.

### Rebuilding

In the process of contributing you will want to sync up with the latest Houston/Codex code and not be working against Docker leftovers. 

These invoke commands will assist you in a clean start: 

Command `invoke docker-compose.rebuild` will rebuild all retained Codex services.

Command `invoke docker-compose.rebuild-gitlab` is a targeted rebuild to the Gitlab component used for asset storage.

### Other Actions

Be sure to list other invoke commands with `invoke -l` while in the virtual environment and inspect them. 
There are many useful tools here that can save you time. 
