# CODEX deployment

A deployment of CODEX with all the moving parts.

## Local (via docker-compose)

The configuration is by environment variable via the `.env` file in this directory.

### development interface

For development purposes, this setup exposes each of the services as follows:

<!-- don't use port 80 when defining any hosts -->
- EDM - http://localhost:81/
- Sage (Wildbook-IA) - http://localhost:82/
- Houston - http://localhost:83/
- pgAdmin - http://localhost:8000/
- CODEX (frontend) - http://localhost:84/
- CODEX (api docs) - http://localhost:84/api/v1/
- GitLab - http://localhost:85

### Usage

#### Running the applications

Run the deployment locally with docker-compose:

    docker-compose up -d && sleep 5 && docker-compose ps

Note, the composition can take several minutes to successfully come up.
There are a number of operations setting up the services and automating the connections between them.
All re-ups should be relatively fast.

#### Cleaning up

Cleanup volumes:

    docker volume rm $(docker volume ls -q | grep codex_)

Big red button:

    docker-compose down && docker volume rm $(docker volume ls -q | grep codex_)

Precision nuke example:

    docker-compose stop houston && docker-compose rm -f houston && docker volume rm codex_houston-var

#### Running the tests

Place yourself in a shell within the houston container:

    docker-compose exec db psql -U postgres -d houston -c "drop schema public cascade; create schema public;"
    docker-compose exec houston /bin/bash -c "invoke app.db.upgrade --no-backup; invoke app.db.init-development-data --no-upgrade-db; invoke app.initialize.initialize-gitlab-submissions --email test@localhost"
    docker-compose exec db psql -U postgres -d houston -c "drop schema public cascade; create schema public;"

This round about way of initializing the required gitlab repositories is necessary.
We'll need TODO something to set these repositories up within the testing framework rather than outside of it.

Start a shell within the houston container:

    docker-compose exec houston /bin/bash

Now within the houston container you can run the tests:

    unset FLASK_CONFIG
    pytest

Note, `FLASK_CONFIG` is unset here because it conflicts with the tests.
It's something that will need fixed. This is simply a work around until then.
