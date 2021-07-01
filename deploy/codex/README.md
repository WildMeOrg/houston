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

#### Running the applications without gitlab

The gitlab container uses a lot of resources and can be impractical to
run on a development machine.  It is possible to run the applications
without gitlab by doing:

    docker-compose -f docker-compose.yml -f docker-compose.no-gitlab.yml up -d

This tells `docker-compose` to use both `docker-compose.yml` and
`docker-compose.no-gitlab.yml`.  This is really only necessary for
`docker-compose up` and `docker-compose run`.  For `docker-compose ps`
or `docker-compose exec`, there's no need to include
`-f docker-compose.yml -f docker-compose.no-gitlab.yml`.

#### Cleaning up

Cleanup volumes:

    docker volume rm $(docker volume ls -q | grep codex_)

Big red button:

    docker-compose down && docker volume rm $(docker volume ls -q | grep codex_)

Precision nuke example:

    docker-compose stop houston && docker-compose rm -f houston && docker volume rm codex_houston-var

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
