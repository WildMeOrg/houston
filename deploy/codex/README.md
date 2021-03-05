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

### Usage

Run the deployment locally with docker-compose:
    docker-compose up -d && sleep 5 && docker-compose ps

Cleanup volumes:
    docker volume rm $(docker volume ls -q | grep codex_)

Big red button:
    docker-compose down && docker volume rm $(docker volume ls -q | grep codex_)

Precision nuke:
    SRVC=houston docker-compose stop ${SRVC} && docker-compose rm -f houston && docker volume rm codex_${SRVC}-var
