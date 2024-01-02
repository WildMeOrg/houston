![Tests](https://github.com/WildMeOrg/houston/workflows/Testing/badge.svg?branch=develop)
[![Codecov](https://codecov.io/gh/WildMeOrg/houston/branch/develop/graph/badge.svg?token=M8MR14ED6V)](https://codecov.io/gh/WildMeOrg/houston)
[![Docker Nightly](https://img.shields.io/docker/image-size/wildme/houston/nightly)](https://hub.docker.com/r/wildme/houston)

# Wild Me - Houston Backend Server

Houston is a REST API component within the CODEX application suite. It is used to glue the frontend  [Wildbook-IA](https://github.com/WildMeOrg/wildbook-ia).

For a high-level explanation of the application in relation to other CODEX applications read the documentation at [CODEX - Houston](https://docs.wildme.org/docs/developers/houston).


## About this implementation

This project showcases my vision on how the RESTful API server should be
implemented.

The goals that were achieved in this example:

* RESTful API server should be self-documented using OpenAPI (fka Swagger) specifications, so interactive documentation UI is in place
* Authentication is handled with OAuth2 and using Resource Owner Password Credentials Grant (Password Flow) for first-party clients makes it usable not only for third-party "external" apps
* Permissions are handled (and automaticaly documented)
* PATCH method can be handled accordingly to [RFC 6902](http://tools.ietf.org/html/rfc6902)
* Extensive testing with good code coverage.

The package Flask-RESTX has been patched (see `flask_restx_patched` folder), so it can handle Marshmallow schemas and Webargs arguments.

## Pull Request Workflow

### Fork Houston
To start, you will need to be signed in to your GitHub account, have admin access to your OS's terminal, and have Git installed.
1. From your browser, in the top right corner of the [Houston repo](https://github.com/WildMeOrg/houston), click the **Fork** button. Confirm to be redirected to your own fork (check the url for your USERNAME in the namespace).
1. In your terminal, enter the command `git clone --recurse-submodules https://github.com/USERNAME/houston`
1. Once the Houston directory become available in your working directory, move to it with the command `cd Houston`
1. Add a reference to the original repo, denoting it as the upstream repo.
`git remote add upstream https://github.com/WildMeOrg/houston`
`git fetch upstream`

### Create Local Branch
You will want to work in a branch when doing any feature development you want to provide to the original project.
1. Verify you are on the main branch. The branch you have checked out will be used as the base for your new branch, so you typically want to start from main.
`git checkout main`
1. Create your feature branch. It can be helpful to include the issue number (ISSUENUMBER) you are working to address.
`git branch ISSUENUMBER-FEATUREBRANCHNAME`
1. Change to your feature branch so your changes are grouped together.
`git checkout ISSUENUMBER-FEATUREBRANCHNAME`
1. Update your branch (this is not needed if you just created new branch, but is a good habit to get into).
` git pull --rebase upstream main`

### Making Local Changes
Make the code changes necessary for the issue you're working on. The following git commands may prove useful.

* `git log`: lastest commits of current branch
* `git status`: current staged and unstaged modifications
* `git diff --staged`:  the differences between the staging area and the last commit
* `git add <filename>: add files that have changes to staging in preparation for commit
* `git commit`: commits the stagged files, opens a text editor for you to write a commit log

### Submit PR
Up to this point, all changes have been done to your local copy of Houston. You need to push the new commits to a remote branch to start the PR process.

1. Now's the time clean up your PR if you choose to squash commits or rebase. If you're looking for more information on these practices, see this [pull request tutorial](https://yangsu.github.io/pull-request-tutorial/).
1. Push to the remote version of your branch ` git push <remote> <local branch>`
`git push origin ISSUENUMBER-FEATUREBRANCHNAME`
1. When prompted, provide your username and GitHub Personal Access Token. If you do not have a GitHub Personal Access Token, or do not have one with the correct permissions for your newly forked repository, you will need to [create a Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token).
1. Check the fork's page on GitHub to verify that you see a new branch with your added commits. You should see a line saying "This branch is X commits ahead" and a **Pull request** link. 
1. Click the **Pull request** link to open a form that says "Able to merge". (If it says there are merge conflicts, go the [Wild Me Development Discord](https://discord.gg/zw4tr3RE4R) for help).
1. Use an explicit title for the PR and provide details in the comment area. Details can include text, or images, and should provide details as to what was done and why design decisions were made.
1. Click **Create a pull request**. 
 
### Respond to feedback
At this point, it's on us to get you feedback on your submission! Someone from the Wild Me team will review the project and provide any feedback that may be necessary. If changes are recommended, you'll need to checkout the branch you were working from, update the branch, and make these changes locally. If no changes are needed, we'll take care of the final merge.


See [Contributing to Houston](CONTRIBUTING.md) for code styles and other information.

## Project's Code Structure

See [Project Structure](docs/project_file_structure.md)

## Background and Periodic Tasks using Celery

See [Background and Periodic Tasks](docs/background_tasks.md)

## Installation

### Using docker-compose (recommended)

#### Setup

```bash
git clone --recurse-submodules https://github.com/WildMeOrg/houston.git

# Option 1 - Activate Codex App
./scripts/codex/activate.sh
docker-compose up

# Option 2 - Use Codex Config Explicitly
docker-compose -f docker-compose.codex.yml --env-file .env.codex up
```

Surf to http://localhost:84/. If you are having issues, see the [docker-compose debugging](docs/docker_compose_debugging.md) docs.

### Installing from source

#### Development Setup Note

Installation of Houston and the other components of Codex from source is intended to facilitate development leveraging the docker-compose environment.

See **Development Environment** section in [Contributing to Houston](CONTRIBUTING.md)
for details. Full deployment of Codex outside docker-compose orchestration is not supported, and any
changes should not be considered finished until they have been tested in the docker-compose environment.

#### Clone the Project

```bash
git clone --recurse-submodules https://github.com/WildMeOrg/houston.git
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


## Usage

Open online interactive API documentation:
[http://127.0.0.1:5000/api/v1/](http://127.0.0.1:5000/api/v1/)

Autogenerated swagger config is always available from
[http://127.0.0.1:5000/api/v1/swagger.json](http://127.0.0.1:5000/api/v1/swagger.json)

NOTE: Use On/Off switch in documentation to sign in.

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

## Dependencies

### Project Dependencies

This project requires either [**Python**](https://www.python.org/) >= 3.7 or Docker.

The [_tus_](https://tus.io) portions of this application require [**Redis**](https://redis.io/) to facilitate resumable file uploads.

[**GitLab**](https://about.gitlab.com/install/) (community edition) is required for asset and submission storage and management.

[**Postgres**](https://www.postgresql.org/) is an optional dependency that can be used for a highly reliable scaled database solution.


## Documentation

### Build the documentation

To build and view the documentation use the following commands:

```
cd docs
pip install -r requirements.txt
make html
open _build/html/index.html
```


## Site Settings

There are some site settings that some features are dependent on:

| Site setting name        | Environment variable             |         |
|-------------------------|----------------------------------|------------|
| `flatfileKey`            | `FLATFILE_KEY`                   | Flatfile API key for bulk upload |
| `recaptchaPublicKey`     | `RECAPTCHA_PUBLIC_KEY`           | Recaptcha site key (disabled if empty) |
| `recaptchaSecretKey`     | `RECAPTCHA_SECRET_KEY`           | Recaptcha secret key |
| `googleMapsApiKey`       | `GOOGLE_MAPS_API_KEY`            | Google maps API key (sighting report form) |
| `email_service`          | `DEFAULT_EMAIL_SERVICE`          | e.g. "mailchimp" |
| `email_service_username` | `DEFAULT_EMAIL_SERVICE_USERNAME` | mailchimp username |
| `email_service_password` | `DEFAULT_EMAIL_SERVICE_PASSWORD` | mailchimp password |

The way these site settings work is:

 - look in the database table `site_setting` for key, return value if exists
 - if not in the database, return the environment variable

For example, you can set the environment variables in the `.env` file or use `docker-compose.override.yml` to override the environment variables without having to edit any checked in files.  Run `docker-compose up -d` to update any affected containers.


## reCAPTCHA

Register at https://www.google.com/recaptcha/admin/create for `reCAPTCHA v3`.

Add the site (public) key and secret key to `docker-compose.override.yml`:

```
services:
  houston:
    environment:
      RECAPTCHA_PUBLIC_KEY: "recaptcha-public-key"
      RECAPTCHA_SECRET_KEY: "recaptcha-secret-key"
```

`docker-compose up -d` to update running services.

Settings can also be set via `SiteSetting`, the keys are
`recaptchaPublicKey` and `recaptchaSecretKey`.

## License

This software is subject to the provisions of Apache License Version 2.0 (APL). See `LICENSE` for details. Copyright (c) 2020 Wild Me
