#!/bin/bash
# Assumes it is run from the project root.

set -e

# Copy dist packages out of _frontend repo and deploy
BASE_INSTALL_PATH="app/static/swagger-ui/"


function build_in_docker() {
    set -ex

    echo "Running the Swagger build within Docker..."
    docker pull node:latest
    docker run --rm -v $(pwd)/:/code -w /code node:latest /bin/bash -c "./scripts/build.swagger.sh --exec"
    echo "Finished running the build within Docker"
}

function build() {
    set -ex

    # Update code
    pushd docs/

    # Remove any pre-downloaded modules
    rm -rf node_modules/
    rm -rf package-lock.json
    rm -rf swagger_static/

    mkdir -p swagger_static/

    # Install dependencies fresh
    npm cache clean -f

    npm install -g npm@latest

    npm install --legacy-peer-deps

    npm audit fix --force

    # Copy files
    cp node_modules/swagger-ui-dist/{swagger-ui*.{css,js}{,.map},favicon*.png,oauth2-redirect.html} swagger_static/

    cp node_modules/typeface-droid-sans/index.css swagger_static/droid-sans.css

    cp -R node_modules/typeface-droid-sans/files swagger_static/

    popd
}

function install() {
    set -ex

    rm -rf ${BASE_INSTALL_PATH}

    mkdir -p ${BASE_INSTALL_PATH}

    cp -R docs/swagger_static/* ${BASE_INSTALL_PATH}
}

# Build within a Node container
if [[ "$1" != "--exec" ]]; then
    build_in_docker
    install
    exit $?
else
    build
fi
