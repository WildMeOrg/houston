#!/bin/bash

set -xe

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

# test app.boilerplates.crud-module
rm -rf app/modules/testapp
coverage run --append `which invoke` app.boilerplates.crud-module
coverage run --append `which invoke` app.boilerplates.crud-module --module-name=test-app
coverage run --append `which invoke` app.boilerplates.crud-module --module-name=testapp
coverage run --append `which invoke` app.boilerplates.crud-module --module-name=testapp

# test app.config.*
coverage run --append `which invoke` app.config.show

# test interpreter shells
echo | coverage run --append `which invoke` app.shell
echo | coverage run --append `which invoke` app.dev.embed

# test app.endpoints.*
coverage run --append `which invoke` app.endpoints.list

# test app.swagger.*
coverage run --append `which invoke` app.swagger.export
if which docker
then
  coverage run --append `which invoke` app.swagger.codegen --language python --version 1.0.0
fi

# test integrations check
if [ "$HOUSTON_APP_CONTEXT" == 'codex' ]; then
    # `|| true` is used to ignore integration fail with gitlab
    coverage run --append `which invoke` codex.integrations.check || true
    coverage run --append `which invoke` codex.integrations.check-celery || true
fi

# test app.users.*
echo password | coverage run --append `which invoke` app.users.create-user user@example.org
echo password | coverage run --append `which invoke` app.users.create-user test@wildme.org
coverage run --append `which invoke` app.users.list-all
coverage run --append `which invoke` app.users.add-role --role=Researcher --email=user@example.org
coverage run --append `which invoke` app.users.remove-role --role=Researcher --email=user@example.org

# test app.assets.*
coverage run --append `which invoke` app.assets.list-all

# test codex.consistency.*
if [ "$HOUSTON_APP_CONTEXT" == 'codex' ]; then
    coverage run --append `which invoke` codex.consistency.all
    coverage run --append `which invoke` codex.consistency.user-staff-permissions
fi

# test codex.*
if [ "$HOUSTON_APP_CONTEXT" == 'codex' ]; then
    coverage run --append `which invoke` codex.asset-groups.list-all
    coverage run --append `which invoke` codex.encounters.list-all
    coverage run --append `which invoke` codex.organizations.list-all
    coverage run --append `which invoke` codex.projects.list-all
fi

coverage run --append `which invoke` dependencies.install-all-ui --on-error skip
