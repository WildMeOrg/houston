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

# test app.db.*
coverage run --append `which invoke` app.db.upgrade --no-backup
if [ "$SQLALCHEMY_DATABASE_URI" == "" ]
then
    coverage run --append `which invoke` app.db.init-development-data
else
    coverage run --append `which invoke` app.db.init-development-data --no-upgrade-db
fi
coverage run --append `which invoke` app.db.show
coverage run --append `which invoke` app.db.history
coverage run --append `which invoke` app.db.migrate
coverage run --append `which invoke` app.db.heads
coverage run --append `which invoke` app.db.branches
coverage run --append `which invoke` app.db.current
coverage run --append `which invoke` app.db.revision
rm -rf test-db-init
coverage run --append `which invoke` app.db.init --directory=test-db-init

# make sure swagger-ui.zip doesn't exist
rm -f app/static/bower/swagger-ui.zip
coverage run --append `which invoke` app.dependencies.install-swagger-ui --force

# test app.boilerplates.crud-module
rm -rf app/modules/testapp
coverage run --append `which invoke` app.boilerplates.crud-module
coverage run --append `which invoke` app.boilerplates.crud-module --module-name=test-app
coverage run --append `which invoke` app.boilerplates.crud-module --module-name=testapp
coverage run --append `which invoke` app.boilerplates.crud-module --module-name=testapp

# test app.config.*
coverage run --append `which invoke` app.config.set --key=BASE_URL --value=http://localhost/
coverage run --append `which invoke` app.config.list
coverage run --append `which invoke` app.config.forget --key=BASE_URL

# test app.env.enter
if [ "$SQLALCHEMY_DATABASE_URI" == "" ]
then
    echo | coverage run --append `which invoke` app.env.enter --no-install-dependencies
    echo | coverage run --append `which invoke` app.env.enter
else
    echo | coverage run --append `which invoke` app.env.enter --no-install-dependencies --no-upgrade-db
    echo | coverage run --append `which invoke` app.env.enter --no-upgrade-db
fi

echo | coverage run --append `which invoke` app.dev.embed
coverage run --append `which invoke` app.run.warmup
coverage run --append `which invoke` app.projects.list-all

# test app.endpoints.*
coverage run --append `which invoke` app.endpoints.list

# test app.swagger.*
coverage run --append `which invoke` app.swagger.export
coverage run --append `which invoke` app.swagger.codegen --language python --version 1.0.0

# test app.users.*
echo password | coverage run --append `which invoke` app.users.create-user user@example.org
echo password | coverage run --append `which invoke` app.users.create-user test@wildme.org
coverage run --append `which invoke` app.users.list-all
coverage run --append `which invoke` app.users.add-role --role=Researcher --email=user@example.org
coverage run --append `which invoke` app.users.remove-role --role=Researcher --email=user@example.org

# test app.consistency.*
coverage run --append `which invoke` app.consistency.all
coverage run --append `which invoke` app.consistency.user-staff-permissions
coverage run --append `which invoke` app.consistency.cleanup-gitlab --dryrun

# test app.submissions.*
coverage run --append `which invoke` app.submissions.create-submission-from-path --path=tests/submissions/test-000/ || echo 'Expected failure'
coverage run --append `which invoke` app.submissions.create-submission-from-path --path=tests/does-not-exist/ --email=user@example.org || echo 'Expected failure'
coverage run --append `which invoke` app.submissions.create-submission-from-path --path=tests/submissions/test-000/ --email=user@example.org
coverage run --append `which invoke` app.submissions.clone-submission-from-gitlab --guid=4d7669ea-9fbe-4f87-be14-25b5391f7333 || echo 'Expected failure'
coverage run --append `which invoke` app.submissions.clone-submission-from-gitlab --guid=4d7669ea-0000-4f87-be14-25b5391f7333 --email=user@example.org || echo 'Expected failure'
coverage run --append `which invoke` app.submissions.clone-submission-from-gitlab --guid=4d7669ea-9fbe-4f87-be14-25b5391f7333 --email=user@example.org
coverage run --append `which invoke` app.submissions.clone-submission-from-gitlab --guid=4d7669ea-9fbe-4f87-be14-25b5391f7333 --email=user@example.org
coverage run --append `which invoke` app.submissions.list-all

coverage run --append `which invoke` app.organizations.list-all
coverage run --append `which invoke` app.assets.list-all
coverage run --append `which invoke` app.encounters.list-all
