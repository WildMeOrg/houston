![Tests](https://github.com/WildMeOrg/houston/workflows/Testing/badge.svg?branch=develop)
[![Codecov](https://codecov.io/gh/WildMeOrg/houston/branch/develop/graph/badge.svg?token=M8MR14ED6V)](https://codecov.io/gh/WildMeOrg/houston)
[![Docker Nightly](https://img.shields.io/docker/image-size/wildme/houston/nightly)](https://hub.docker.com/r/wildme/houston)

# Wild Me - Houston Backend Server

Houston is a REST API component within the CODEX application suite. It is used to glue the frontend  [Wildbook-IA](https://github.com/WildMeOrg/wildbook-ia).

For a high-level explanation of the application in relation to other CODEX applications read the documentation at [CODEX - Houston](https://docs.wildme.org/docs/developers/houston).


## About this implementation

* RESTful API server should be self-documented using OpenAPI (fka Swagger) specifications, so interactive documentation UI is in place
* Authentication is handled with OAuth2 and using Resource Owner Password Credentials Grant (Password Flow) for first-party clients makes it usable not only for third-party "external" apps
* Permissions are handled (and automaticaly documented)
* PATCH method can be handled accordingly to [RFC 6902](http://tools.ietf.org/html/rfc6902)
* Extensive testing with good code coverage.
* The package Flask-RESTX has been patched (see `flask_restx_patched` folder), so it can handle Marshmallow schemas and Webargs arguments.

## Pull Request Workflow

### Fork Houston
To start, you will need to be signed in to your GitHub account, have admin access to your OS's terminal, and have Git installed.
1. From your browser, in the top right corner of the [Houston repo](https://github.com/WildMeOrg/houston), click the **Fork** button. Confirm to be redirected to your own fork (check the url for your USERNAME in the namespace).
1. In your terminal, enter the command `git clone --recurse-submodules https://github.com/USERNAME/houston`
1. Once the houston directory become available in your working directory, move to it with the command `cd houston`
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
` git pull upstream main`

### Making Local Changes
Make the code changes necessary for the issue you're working on. The following git commands may prove useful.

* `git log`: lastest commits of current branch
* `git status`: current staged and unstaged modifications
* `git diff --staged`:  the differences between the staging area and the last commit
* `git add <filename>: add files that have changes to staging in preparation for commit
* `git commit`: commits the stagged files, opens a text editor for you to write a commit log

#### Using Docker for your Dev Environment
Set up the tools needed:
1. Ensure that you are in the `houston` directory
1. If you have not already, install docker ex: `sudo apt install docker`
1. If you have not already, install docker-compose ex: `sudo apt install docker-compose`
1. Install pre-commit to set up your linter. This will run automatically for any PR.
`pip install pre-commit`
1. Enter command `./scripts/codex/activate.sh`
1. `sudo sysctl -w vm.max_map_count=262144`

Manage your container:
1. Enter `docker-compose up` to bring up the container.
1. In your browser, visit any of the following ports to confirm your system is running.
  * Sage (Wildbook-IA) - http://localhost:82/
  * Houston - http://localhost:83/houston/
  * CODEX (frontend) - http://localhost:84/
  * CODEX (api docs) - http://localhost:84/api/v1/
1. Enter `docker-compose down` to bring down the container.
1. To rebuild your docker image, enter `docker-compose up -build`

#### App Setup
1. At http://localhost:84, work through the admin initial setup.
1. Navigate to Site Settings > Custom Fields
1. Add Species
1. Add Regions

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
At this point, it's on us to get you feedback on your submission! Someone from the Wild Me team will review the project and provide any feedback that may be necessary. If changes are recommended, you'll need to checkout the branch you were working from, update the branch, and make these changes locally.

1. `git checkout ISSUENUMBER-FEATUREBRANCHNAME`
1. `git pull upstream main`
1. Make required changes
1. `git add <filename>` for all files impacted by changes
1. Determine which method would be most appropriate for updating your PR  
  * `git commit --ammend` if the changes are small stylistic changes
  * `git commit` if the changes involved significant rework and require additional details

See [Contributing to Houston](CONTRIBUTING.md) for code styles and other information.

## Project's Code Structure

See [Project Structure](docs/project_file_structure.md)

## Background and Periodic Tasks using Celery

See [Background and Periodic Tasks](docs/background_tasks.md)


## Documentation

### Interactive Documentation
Open online interactive API documentation:
[http://127.0.0.1:5000/api/v1/](http://127.0.0.1:5000/api/v1/)

Autogenerated swagger config is always available from
[http://127.0.0.1:5000/api/v1/swagger.json](http://127.0.0.1:5000/api/v1/swagger.json)

NOTE: Use On/Off switch in documentation to sign in.

### Static documentation

To build and view the documentation use the following commands:

```
cd docs
pip install -r requirements.txt
make html
open _build/html/index.html
```

## Dependencies

### Project Dependencies

This project requires either [**Python**](https://www.python.org/) >= 3.7 or Docker.

The [_tus_](https://tus.io) portions of this application require [**Redis**](https://redis.io/) to facilitate resumable file uploads.

[**GitLab**](https://about.gitlab.com/install/) (community edition) is required for asset and submission storage and management.

[**Postgres**](https://www.postgresql.org/) is an optional dependency that can be used for a highly reliable scaled database solution.


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

This software is subject to the provisions of MIT License. See `LICENSE` for details. Copyright (c) 2023 Wild Me