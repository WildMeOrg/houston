#!/bin/bash

set -xe
# Set up GITLAB_REMOTE_LOGIN_PAT in config.py
if [ "$GITLAB_REMOTE_LOGIN_PAT" != "" ]
then
    sed -i "s/GITLAB_REMOTE_LOGIN_PAT.*/GITLAB_REMOTE_LOGIN_PAT = '$GITLAB_REMOTE_LOGIN_PAT'/" _db/secrets.py
fi
# We need to have a persistent sqlite database to run these tasks
if [ "$SQLALCHEMY_DATABASE_URI" == "sqlite://" ]
then
    SQLALCHEMY_DATABASE_URI=''
    rm -f _db/database.sqlite3
else
    python -c 'import os; import sqlalchemy; sqlalchemy.create_engine(os.environ["SQLALCHEMY_DATABASE_URI"]).execute("DROP TABLE IF EXISTS alembic_version")'
fi

# test codex.db.*
coverage run --append `which invoke` codex.db.upgrade --no-backup
if [ "$SQLALCHEMY_DATABASE_URI" == "" ]
then
    coverage run --append `which invoke` codex.db.init-development-data
else
    coverage run --append `which invoke` codex.db.init-development-data --no-upgrade-db
fi
coverage run --append `which invoke` codex.db.show
coverage run --append `which invoke` codex.db.history
coverage run --append `which invoke` codex.db.migrate
coverage run --append `which invoke` codex.db.heads
coverage run --append `which invoke` codex.db.branches
coverage run --append `which invoke` codex.db.current
coverage run --append `which invoke` codex.db.revision
rm -rf test-db-init
coverage run --append `which invoke` codex.db.init --directory=test-db-init

# test codex.boilerplates.crud-module
rm -rf app/modules/testapp
coverage run --append `which invoke` codex.boilerplates.crud-module
coverage run --append `which invoke` codex.boilerplates.crud-module --module-name=test-app
coverage run --append `which invoke` codex.boilerplates.crud-module --module-name=testapp
coverage run --append `which invoke` codex.boilerplates.crud-module --module-name=testapp

# test codex.config.*
coverage run --append `which invoke` codex.config.set --key=BASE_URL --value=http://localhost/
coverage run --append `which invoke` codex.config.list
coverage run --append `which invoke` codex.config.forget --key=BASE_URL
coverage run --append `which invoke` codex.config.show

# test interpreter shells
echo | coverage run --append `which invoke` codex.shell
echo | coverage run --append `which invoke` codex.dev.embed

coverage run --append `which invoke` codex.run.warmup --print-routes
coverage run --append `which invoke` codex.projects.list-all

# test codex.endpoints.*
coverage run --append `which invoke` codex.endpoints.list

# test codex.swagger.*
coverage run --append `which invoke` codex.swagger.export
if which docker
then
  coverage run --append `which invoke` codex.swagger.codegen --language python --version 1.0.0
fi

# test codex.users.*
echo password | coverage run --append `which invoke` codex.users.create-user user@example.org
echo password | coverage run --append `which invoke` codex.users.create-user test@wildme.org
coverage run --append `which invoke` codex.users.list-all
coverage run --append `which invoke` codex.users.add-role --role=Researcher --email=user@example.org
coverage run --append `which invoke` codex.users.remove-role --role=Researcher --email=user@example.org

# test codex.consistency.*
coverage run --append `which invoke` codex.consistency.all
coverage run --append `which invoke` codex.consistency.user-staff-permissions
coverage run --append `which invoke` codex.consistency.cleanup-gitlab --dryrun

coverage run --append `which invoke` codex.organizations.list-all
coverage run --append `which invoke` codex.assets.list-all
coverage run --append `which invoke` codex.encounters.list-all

coverage run --append `which invoke` dependencies.install-all-ui --on-error skip
